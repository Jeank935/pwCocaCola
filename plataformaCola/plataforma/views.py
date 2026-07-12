import csv
from io import BytesIO
from datetime import timedelta
from functools import wraps
from xml.sax.saxutils import escape

from django.contrib import messages
from django.contrib.auth.hashers import check_password
from django.db import transaction
from django.db.models import Count, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
    ComercioForm,
    LoginForm,
    RegistroComercioForm,
    ReporteAdministrativoFiltroForm,
    ReporteFiltroForm,
)
from .incentivos import (
    calcular_descuento_pedido,
    evaluar_bonificacion_frecuencia,
    recalcular_categoria,
    siguiente_categoria,
)
from .models import (
    Comercio,
    DetallePedido,
    Entrega,
    Notificacion,
    Pedido,
    Producto,
    PuntosFidelidad,
    Ruta,
    Usuario,
)


def obtener_usuario_actual(request):
    usuario_id = request.session.get("usuario_id")
    if not usuario_id:
        return None
    usuario = Usuario.objects.select_related("comercio").filter(id=usuario_id).first()
    if usuario and request.session.get("usuario_rol") != usuario.rol:
        request.session["usuario_rol"] = usuario.rol
        request.session.modified = True
    return usuario


def es_usuario_logistica(usuario):
    return usuario.rol.strip().lower() == "logistica"


def es_usuario_administrador(usuario):
    return usuario.rol.strip().lower() == "administrador"


def comercio_requerido(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        usuario = obtener_usuario_actual(request)
        if not usuario:
            messages.warning(request, "Inicia sesion para continuar.")
            return redirect("login")
        if es_usuario_logistica(usuario):
            return redirect("pedidos_logistica")
        if es_usuario_administrador(usuario):
            return redirect("dashboard_administracion")
        if not usuario.comercio_id:
            messages.error(request, "El usuario no tiene un comercio asociado.")
            return redirect("logout")
        request.usuario_plataforma = usuario
        request.comercio_actual = usuario.comercio
        return view_func(request, *args, **kwargs)

    return wrapper


def logistica_requerida(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        usuario = obtener_usuario_actual(request)
        if not usuario:
            messages.warning(request, "Inicia sesion para continuar.")
            return redirect("login")
        if not es_usuario_logistica(usuario):
            if es_usuario_administrador(usuario):
                return redirect("dashboard_administracion")
            messages.warning(request, "Esta seccion es exclusiva para logistica.")
            return redirect("index")
        request.usuario_plataforma = usuario
        return view_func(request, *args, **kwargs)

    return wrapper


def administracion_requerida(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        usuario = obtener_usuario_actual(request)
        if not usuario:
            messages.warning(request, "Inicia sesion para continuar.")
            return redirect("login")
        if not es_usuario_administrador(usuario):
            messages.warning(request, "Esta seccion es exclusiva para administracion.")
            return redirect("index")
        request.usuario_plataforma = usuario
        return view_func(request, *args, **kwargs)

    return wrapper


def obtener_carrito(request):
    carrito = request.session.setdefault("carrito", {})
    if "carrito_cantidad" not in request.session:
        request.session["carrito_cantidad"] = contar_productos_carrito(carrito)
        request.session.modified = True
    return carrito


def contar_productos_carrito(carrito):
    total = 0
    for cantidad in carrito.values():
        try:
            if int(cantidad) > 0:
                total += 1
        except (TypeError, ValueError):
            continue
    return total


def guardar_carrito(request, carrito):
    request.session["carrito"] = carrito
    request.session["carrito_cantidad"] = contar_productos_carrito(carrito)
    request.session.modified = True


def obtener_items_carrito(carrito):
    productos = Producto.objects.filter(id__in=carrito.keys(), activo=True).order_by("nombre")
    items = []
    total = 0
    for producto in productos:
        cantidad = int(carrito.get(str(producto.id), 0))
        if cantidad <= 0:
            continue
        subtotal = producto.precio * cantidad
        total += subtotal
        items.append(
            {
                "producto": producto,
                "cantidad": cantidad,
                "subtotal": subtotal,
            }
        )
    return items, total


def index(request):
    usuario = obtener_usuario_actual(request)
    if usuario and es_usuario_administrador(usuario):
        return redirect("dashboard_administracion")
    if usuario and es_usuario_logistica(usuario):
        return redirect("pedidos_logistica")

    productos_activos = Producto.objects.filter(activo=True).count()
    pedidos_total = Pedido.objects.count()

    contexto = {
        "usuario": usuario,
        "productos_activos": productos_activos,
        "pedidos_total": pedidos_total,
    }

    if usuario:
        comercio = usuario.comercio
        pedidos = Pedido.objects.filter(comercio=comercio).order_by("-fecha")[:5]
        contexto.update(
            {
                "comercio": comercio,
                "pedidos_recientes": pedidos,
                "notificaciones": comercio.notificaciones.order_by("-enviado_en")[:5],
            }
        )

    return render(request, "plataforma/index.html", contexto)


def registro(request):
    if obtener_usuario_actual(request):
        return redirect("index")

    form = RegistroComercioForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        usuario = form.save()
        request.session["usuario_id"] = usuario.id
        messages.success(request, "Registro completado. Bienvenido a ISBEN Solution.")
        return redirect("index")

    return render(request, "plataforma/registro.html", {"form": form})


def iniciar_sesion(request):
    if obtener_usuario_actual(request):
        return redirect("index")

    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].strip().lower()
        password = form.cleaned_data["password"]
        usuario = Usuario.objects.select_related("comercio").filter(email=email).first()

        if usuario and check_password(password, usuario.password_hash):
            usuario.ultima_sesion = timezone.now()
            usuario.save(update_fields=["ultima_sesion"])
            request.session["usuario_id"] = usuario.id
            request.session["usuario_rol"] = usuario.rol
            messages.success(request, "Sesion iniciada correctamente.")
            if es_usuario_administrador(usuario):
                return redirect("dashboard_administracion")
            if es_usuario_logistica(usuario):
                return redirect("pedidos_logistica")
            return redirect("index")

        messages.error(request, "Correo o contrasena incorrectos.")

    return render(request, "plataforma/login.html", {"form": form})


def cerrar_sesion(request):
    request.session.flush()
    messages.success(request, "Sesion cerrada correctamente.")
    return redirect("index")


@comercio_requerido
def catalogo(request):
    busqueda = request.GET.get("q", "").strip()
    productos = Producto.objects.filter(activo=True).order_by("nombre")
    if busqueda:
        productos = productos.filter(nombre__icontains=busqueda)

    return render(
        request,
        "plataforma/catalogo.html",
        {
            "productos": productos,
            "busqueda": busqueda,
            "carrito": obtener_carrito(request),
        },
    )


@comercio_requerido
def agregar_producto(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id, activo=True)
    try:
        cantidad = int(request.POST.get("cantidad", 1))
    except ValueError:
        cantidad = 0
    if cantidad <= 0:
        messages.warning(request, "Selecciona una cantidad valida.")
        return redirect("catalogo")
    if cantidad > producto.stock:
        messages.warning(request, "La cantidad supera el stock disponible.")
        return redirect("catalogo")

    carrito = obtener_carrito(request)
    cantidad_actual = int(carrito.get(str(producto.id), 0))
    if cantidad_actual + cantidad > producto.stock:
        messages.warning(request, "La cantidad total supera el stock disponible.")
        return redirect("catalogo")

    carrito[str(producto.id)] = cantidad_actual + cantidad
    guardar_carrito(request, carrito)
    messages.success(request, "Producto agregado al pedido.")
    return redirect("catalogo")


@comercio_requerido
def pedido_paso1(request):
    return catalogo(request)


@comercio_requerido
def pedido_paso2(request):
    carrito = obtener_carrito(request)
    items, subtotal = obtener_items_carrito(carrito)

    if not items:
        messages.warning(request, "Agrega productos antes de continuar.")
        return redirect("catalogo")

    calculo = calcular_descuento_pedido(request.comercio_actual, subtotal)

    return render(
        request,
        "plataforma/pedido_resumen.html",
        {
            "items": items,
            "subtotal": subtotal,
            "incentivo": calculo["incentivo"],
            "descuento": calculo["descuento"],
            "descuento_volumen_pct": calculo["descuento_volumen_pct"],
            "bono_categoria_pct": calculo["bono_categoria_pct"],
            "descuento_pct_total": calculo["descuento_pct_total"],
            "total": calculo["total"],
            "cantidad_editable": True,
        },
    )


@comercio_requerido
def pedido_paso3(request):
    carrito = obtener_carrito(request)
    items, subtotal = obtener_items_carrito(carrito)
    if not items:
        messages.warning(request, "No hay productos para confirmar.")
        return redirect("catalogo")

    calculo = calcular_descuento_pedido(request.comercio_actual, subtotal)

    if request.method == "POST":
        with transaction.atomic():
            pedido = Pedido.objects.create(
                fecha=timezone.now(),
                estado="Pendiente",
                monto_total=calculo["total"],
                descuento=calculo["descuento"],
                sincronizado=False,
                comercio=request.comercio_actual,
                usuario=request.usuario_plataforma,
            )

            for item in items:
                producto = item["producto"]
                cantidad = item["cantidad"]
                DetallePedido.objects.create(
                    cantidad=cantidad,
                    precio_unitario=producto.precio,
                    subtotal=item["subtotal"],
                    pedido=pedido,
                    producto=producto,
                )
                producto.stock = max(producto.stock - cantidad, 0)
                producto.save(update_fields=["stock"])

            ruta = Ruta.objects.order_by("id").first()
            if ruta:
                Entrega.objects.create(
                    fecha_estimada=timezone.now() + timedelta(days=2),
                    tipo_confirmacion="Codigo",
                    pedido=pedido,
                    ruta=ruta,
                )

            recalcular_categoria(pedido.comercio)
            evaluar_bonificacion_frecuencia(pedido.comercio, pedido)

        guardar_carrito(request, {})
        messages.success(request, "Pedido confirmado correctamente.")
        return redirect("pedido_detalle", pedido_id=pedido.id)

    return render(
        request,
        "plataforma/pedido_confirmar.html",
        {
            "items": items,
            "subtotal": subtotal,
            "incentivo": calculo["incentivo"],
            "descuento": calculo["descuento"],
            "descuento_volumen_pct": calculo["descuento_volumen_pct"],
            "bono_categoria_pct": calculo["bono_categoria_pct"],
            "descuento_pct_total": calculo["descuento_pct_total"],
            "total": calculo["total"],
        },
    )


@comercio_requerido
def carrito_limpiar(request):
    guardar_carrito(request, {})
    messages.success(request, "Pedido en curso limpiado.")
    return redirect("catalogo")


@comercio_requerido
def eliminar_producto_carrito(request, producto_id):
    if request.method != "POST":
        return redirect("pedido_paso2")

    carrito = obtener_carrito(request)
    producto_key = str(producto_id)
    if producto_key in carrito:
        del carrito[producto_key]
        guardar_carrito(request, carrito)
        messages.success(request, "Producto eliminado del pedido.")

    if contar_productos_carrito(carrito) == 0:
        return redirect("catalogo")

    next_url = request.POST.get("next", "")
    if next_url.startswith("/"):
        return redirect(next_url)
    return redirect("pedido_paso2")


@comercio_requerido
def actualizar_cantidad_carrito(request, producto_id):
    if request.method != "POST":
        return redirect("pedido_paso2")

    producto = get_object_or_404(Producto, id=producto_id, activo=True)
    carrito = obtener_carrito(request)
    producto_key = str(producto.id)
    cantidad_actual = int(carrito.get(producto_key, 0))
    accion = request.POST.get("accion")

    try:
        cantidad_ingresada = int(request.POST.get("cantidad", cantidad_actual))
        cantidad_original = int(request.POST.get("cantidad_original", cantidad_actual))
    except (TypeError, ValueError):
        cantidad_ingresada = 0
        cantidad_original = cantidad_actual

    if cantidad_ingresada != cantidad_original:
        cantidad = cantidad_ingresada
    elif accion == "incrementar":
        cantidad = cantidad_actual + 1
    elif accion == "decrementar":
        cantidad = cantidad_actual - 1
    else:
        cantidad = cantidad_ingresada

    if cantidad <= 0:
        messages.warning(request, "Selecciona una cantidad valida.")
    elif cantidad > producto.stock:
        messages.warning(request, "La cantidad supera el stock disponible.")
    elif producto_key in carrito:
        carrito[producto_key] = cantidad
        guardar_carrito(request, carrito)

    next_url = request.POST.get("next", "")
    if next_url.startswith("/"):
        return redirect(next_url)
    return redirect("pedido_paso2")


@logistica_requerida
def pedidos_logistica(request):
    pedidos_pendientes = (
        Pedido.objects.filter(estado="Pendiente")
        .select_related("comercio", "usuario")
        .prefetch_related("detalles__producto")
        .annotate(
            productos_count=Count("detalles"),
            unidades_total=Sum("detalles__cantidad"),
        )
        .order_by("fecha")
    )
    pedidos_confirmados = (
        Pedido.objects.filter(estado="Confirmado")
        .select_related("comercio")
        .order_by("-fecha")
    )
    return render(
        request,
        "plataforma/pedidos_logistica.html",
        {
            "pedidos_pendientes": pedidos_pendientes,
            "pedidos_pendientes_count": pedidos_pendientes.count(),
            "pedidos_confirmados": pedidos_confirmados,
            "pedidos_confirmados_count": pedidos_confirmados.count(),
        },
    )


@logistica_requerida
def confirmar_pedido_logistica(request, pedido_id):
    if request.method != "POST":
        return redirect("pedidos_logistica")

    pedido = get_object_or_404(Pedido.objects.select_related("comercio"), id=pedido_id)
    actualizado = Pedido.objects.filter(id=pedido.id, estado="Pendiente").update(
        estado="Confirmado"
    )
    if not actualizado:
        messages.warning(request, "El pedido ya fue procesado.")
        return redirect("pedidos_logistica")

    Notificacion.objects.create(
        canal="App",
        mensaje="Tu pedido #%s fue confirmado por logistica." % pedido.id,
        enviado_en=timezone.now(),
        comercio=pedido.comercio,
        pedido=pedido,
    )
    messages.success(request, "Pedido #%s confirmado correctamente." % pedido.id)
    return redirect("pedidos_logistica")


@administracion_requerida
def dashboard_administracion(request):
    resumen = Pedido.objects.aggregate(
        ventas=Sum("monto_total"),
        descuentos=Sum("descuento"),
        pedidos=Count("id"),
    )
    resumen["ventas"] = resumen["ventas"] or 0
    resumen["descuentos"] = resumen["descuentos"] or 0
    resumen["pedidos"] = resumen["pedidos"] or 0
    resumen.update(
        {
            "comercios_activos": Comercio.objects.filter(estado__iexact="Activo").count(),
            "entregas_pendientes": Entrega.objects.filter(
                fecha_real__isnull=True,
                pedido__estado="Confirmado",
            ).count(),
        }
    )

    pedidos_por_estado = (
        Pedido.objects.values("estado")
        .annotate(cantidad=Count("id"), total=Sum("monto_total"))
        .order_by("-cantidad", "estado")
    )
    pedidos_recientes = Pedido.objects.select_related("comercio").order_by("-fecha")[:8]
    productos_bajo_stock = Producto.objects.filter(activo=True, stock__lte=20).order_by(
        "stock", "nombre"
    )[:8]

    return render(
        request,
        "plataforma/dashboard_administracion.html",
        {
            "resumen": resumen,
            "pedidos_por_estado": pedidos_por_estado,
            "pedidos_recientes": pedidos_recientes,
            "productos_bajo_stock": productos_bajo_stock,
        },
    )


@comercio_requerido
def historial_pedidos(request):
    pedidos = Pedido.objects.filter(comercio=request.comercio_actual).order_by("-fecha")
    return render(request, "plataforma/historial.html", {"pedidos": pedidos})


@comercio_requerido
def pedido_detalle(request, pedido_id):
    pedido = get_object_or_404(
        Pedido.objects.prefetch_related("detalles__producto", "entregas__ruta"),
        id=pedido_id,
        comercio=request.comercio_actual,
    )
    return render(request, "plataforma/pedido_detalle.html", {"pedido": pedido})


@comercio_requerido
def reordenar_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id, comercio=request.comercio_actual)
    carrito = {}
    for detalle in pedido.detalles.select_related("producto").filter(producto__activo=True):
        carrito[str(detalle.producto_id)] = detalle.cantidad
    guardar_carrito(request, carrito)
    messages.success(request, "Productos cargados para reordenar.")
    return redirect("pedido_paso2")


@comercio_requerido
def perfil_comercio(request):
    form = ComercioForm(request.POST or None, instance=request.comercio_actual)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Informacion del comercio actualizada.")
        return redirect("perfil")
    return render(request, "plataforma/perfil.html", {"form": form})


@comercio_requerido
def notificaciones(request):
    notificaciones_comercio = request.comercio_actual.notificaciones.select_related(
        "pedido"
    ).order_by("-enviado_en")
    return render(
        request,
        "plataforma/notificaciones.html",
        {"notificaciones": notificaciones_comercio},
    )


@comercio_requerido
def incentivos(request):
    comercio = request.comercio_actual
    incentivos_comercio = comercio.incentivos.order_by("umbral_min")
    puntos_cuenta = PuntosFidelidad.objects.filter(comercio=comercio).first()
    regla_siguiente, volumen_faltante = siguiente_categoria(comercio)

    return render(
        request,
        "plataforma/incentivos.html",
        {
            "incentivos": incentivos_comercio,
            "comercio": comercio,
            "puntos": puntos_cuenta.puntos if puntos_cuenta else 0,
            "siguiente_categoria": regla_siguiente.categoria if regla_siguiente else None,
            "volumen_faltante": volumen_faltante,
        },
    )


def filtrar_pedidos_administracion(request):
    form = ReporteAdministrativoFiltroForm(request.GET or None)
    pedidos = (
        Pedido.objects.select_related("comercio")
        .prefetch_related("entregas__ruta")
        .order_by("-fecha")
    )
    filtros = {
        "zona": "",
        "estado": "",
        "fecha_desde": None,
        "fecha_hasta": None,
    }

    if form.is_valid():
        filtros.update(form.cleaned_data)
        if filtros["zona"]:
            pedidos = pedidos.filter(entregas__ruta__zona=filtros["zona"])
        if filtros["estado"]:
            pedidos = pedidos.filter(estado=filtros["estado"])
        if filtros["fecha_desde"]:
            pedidos = pedidos.filter(fecha__date__gte=filtros["fecha_desde"])
        if filtros["fecha_hasta"]:
            pedidos = pedidos.filter(fecha__date__lte=filtros["fecha_hasta"])

    return form, pedidos.distinct(), filtros


def resumir_pedidos_administracion(pedidos):
    resumen = pedidos.aggregate(
        cantidad=Count("id"),
        total=Sum("monto_total"),
        descuentos=Sum("descuento"),
        comercios=Count("comercio", distinct=True),
    )
    resumen["cantidad"] = resumen["cantidad"] or 0
    resumen["total"] = resumen["total"] or 0
    resumen["descuentos"] = resumen["descuentos"] or 0
    resumen["comercios"] = resumen["comercios"] or 0
    return resumen


def obtener_zonas_pedido(pedido):
    zonas = {
        entrega.ruta.zona
        for entrega in pedido.entregas.all()
        if entrega.ruta_id and entrega.ruta.zona
    }
    return ", ".join(sorted(zonas)) or "Sin ruta"


@administracion_requerida
def reportes_administracion(request):
    form, pedidos, filtros = filtrar_pedidos_administracion(request)
    resumen = resumir_pedidos_administracion(pedidos)
    return render(
        request,
        "plataforma/reportes_administracion.html",
        {
            "form": form,
            "pedidos": pedidos,
            "resumen": resumen,
            "filtros": filtros,
        },
    )


@administracion_requerida
def reportes_administracion_csv(request):
    form, pedidos, filtros = filtrar_pedidos_administracion(request)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        'attachment; filename="reporte_administrativo_pedidos.csv"'
    )

    writer = csv.writer(response)
    writer.writerow(
        ["Pedido", "Fecha", "Estado", "Comercio", "RUC", "Zona", "Descuento", "Total"]
    )
    for pedido in pedidos:
        writer.writerow(
            [
                pedido.id,
                timezone.localtime(pedido.fecha).strftime("%Y-%m-%d %H:%M"),
                pedido.estado,
                pedido.comercio.nombre_comercial,
                pedido.comercio.ruc,
                obtener_zonas_pedido(pedido),
                "%.2f" % pedido.descuento,
                "%.2f" % pedido.monto_total,
            ]
        )

    return response


def construir_pdf_reporte_administrativo(pedidos, resumen, filtros):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = BytesIO()
    page_size = landscape(A4)
    documento = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title="Reporte administrativo de pedidos",
        author="ISBEN Solution",
    )
    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle(
        "TituloISBEN",
        parent=estilos["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#151515"),
        spaceAfter=5 * mm,
    )
    texto = ParagraphStyle(
        "TextoISBEN",
        parent=estilos["BodyText"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#374151"),
    )
    texto_derecha = ParagraphStyle("TextoDerecha", parent=texto, alignment=TA_RIGHT)

    etiquetas_filtro = []
    if filtros.get("zona"):
        etiquetas_filtro.append("Zona: %s" % filtros["zona"])
    if filtros.get("estado"):
        etiquetas_filtro.append("Estado: %s" % filtros["estado"])
    if filtros.get("fecha_desde"):
        etiquetas_filtro.append("Desde: %s" % filtros["fecha_desde"].strftime("%d/%m/%Y"))
    if filtros.get("fecha_hasta"):
        etiquetas_filtro.append("Hasta: %s" % filtros["fecha_hasta"].strftime("%d/%m/%Y"))
    filtros_texto = " | ".join(etiquetas_filtro) or "Sin filtros aplicados"

    historia = [
        Paragraph("Reporte administrativo de pedidos", titulo),
        Paragraph(escape(filtros_texto), texto),
        Spacer(1, 5 * mm),
    ]

    resumen_datos = [
        ["Pedidos", "Comercios", "Ventas", "Descuentos"],
        [
            str(resumen["cantidad"]),
            str(resumen["comercios"]),
            "$%.2f" % resumen["total"],
            "$%.2f" % resumen["descuentos"],
        ],
    ]
    tabla_resumen = Table(resumen_datos, colWidths=[45 * mm] * 4)
    tabla_resumen.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FFC22F")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#151515")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D7DADE")),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    historia.extend([tabla_resumen, Spacer(1, 7 * mm)])

    filas = [["Pedido", "Fecha", "Comercio", "Zona", "Estado", "Descuento", "Total"]]
    for pedido in pedidos:
        filas.append(
            [
                "#%s" % pedido.id,
                timezone.localtime(pedido.fecha).strftime("%d/%m/%Y %H:%M"),
                Paragraph(escape(pedido.comercio.nombre_comercial), texto),
                Paragraph(escape(obtener_zonas_pedido(pedido)), texto),
                pedido.estado,
                Paragraph("$%.2f" % pedido.descuento, texto_derecha),
                Paragraph("$%.2f" % pedido.monto_total, texto_derecha),
            ]
        )
    if len(filas) == 1:
        filas.append(["-", "-", "Sin resultados", "-", "-", "$0.00", "$0.00"])

    tabla = Table(
        filas,
        repeatRows=1,
        colWidths=[16 * mm, 30 * mm, 54 * mm, 39 * mm, 27 * mm, 27 * mm, 27 * mm],
    )
    tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FB4318")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (5, 1), (-1, -1), "RIGHT"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F8FA")]),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D7DADE")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    historia.append(tabla)

    def dibujar_pie(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#E6E8EC"))
        canvas.line(14 * mm, 11 * mm, page_size[0] - 14 * mm, 11 * mm)
        canvas.setFillColor(colors.HexColor("#6B7280"))
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(14 * mm, 7 * mm, "ISBEN Solution - Administracion")
        canvas.drawRightString(page_size[0] - 14 * mm, 7 * mm, "Pagina %s" % doc.page)
        canvas.restoreState()

    documento.build(historia, onFirstPage=dibujar_pie, onLaterPages=dibujar_pie)
    return buffer.getvalue()


@administracion_requerida
def reportes_administracion_pdf(request):
    form, pedidos, filtros = filtrar_pedidos_administracion(request)
    resumen = resumir_pedidos_administracion(pedidos)
    contenido = construir_pdf_reporte_administrativo(pedidos, resumen, filtros)
    response = HttpResponse(contenido, content_type="application/pdf")
    response["Content-Disposition"] = (
        'attachment; filename="reporte_administrativo_pedidos.pdf"'
    )
    return response


def filtrar_pedidos_reporte(request, comercio):
    form = ReporteFiltroForm(request.GET or None)
    pedidos = Pedido.objects.filter(comercio=comercio).order_by("-fecha")

    if form.is_valid():
        estado = form.cleaned_data.get("estado")
        fecha_desde = form.cleaned_data.get("fecha_desde")
        fecha_hasta = form.cleaned_data.get("fecha_hasta")
        if estado:
            pedidos = pedidos.filter(estado__icontains=estado)
        if fecha_desde:
            pedidos = pedidos.filter(fecha__date__gte=fecha_desde)
        if fecha_hasta:
            pedidos = pedidos.filter(fecha__date__lte=fecha_hasta)

    return form, pedidos


@comercio_requerido
def reportes(request):
    form, pedidos = filtrar_pedidos_reporte(request, request.comercio_actual)
    resumen = pedidos.aggregate(total=Sum("monto_total"), cantidad=Count("id"))
    resumen["total"] = resumen["total"] or 0
    resumen["cantidad"] = resumen["cantidad"] or 0
    return render(
        request,
        "plataforma/reportes.html",
        {
            "form": form,
            "pedidos": pedidos,
            "resumen": resumen,
        },
    )


@comercio_requerido
def reportes_csv(request):
    form, pedidos = filtrar_pedidos_reporte(request, request.comercio_actual)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="reporte_pedidos.csv"'

    writer = csv.writer(response)
    writer.writerow(["Pedido", "Fecha", "Estado", "Descuento", "Total"])
    for pedido in pedidos:
        writer.writerow(
            [
                pedido.id,
                pedido.fecha.strftime("%Y-%m-%d %H:%M"),
                pedido.estado,
                pedido.descuento,
                pedido.monto_total,
            ]
        )

    return response

# Create your views here.
