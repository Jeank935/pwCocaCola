import csv
from datetime import timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth.hashers import check_password
from django.db import transaction
from django.db.models import Count, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
    ComercioForm,
    EntregaConfirmacionForm,
    LoginForm,
    RegistroComercioForm,
    ReporteFiltroForm,
)
from .incentivos import (
    calcular_descuento_pedido,
    evaluar_bonificacion_frecuencia,
    recalcular_categoria,
    siguiente_categoria,
)
from .models import DetallePedido, Entrega, Pedido, Producto, PuntosFidelidad, Ruta, Usuario


def obtener_usuario_actual(request):
    usuario_id = request.session.get("usuario_id")
    if not usuario_id:
        return None
    return Usuario.objects.select_related("comercio").filter(id=usuario_id).first()


def comercio_requerido(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        usuario = obtener_usuario_actual(request)
        if not usuario:
            messages.warning(request, "Inicia sesion para continuar.")
            return redirect("login")
        request.usuario_plataforma = usuario
        request.comercio_actual = usuario.comercio
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
            messages.success(request, "Sesion iniciada correctamente.")
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
<<<<<<< HEAD
            "incentivo": calculo["incentivo"],
            "descuento": calculo["descuento"],
            "descuento_volumen_pct": calculo["descuento_volumen_pct"],
            "bono_categoria_pct": calculo["bono_categoria_pct"],
            "descuento_pct_total": calculo["descuento_pct_total"],
            "total": calculo["total"],
=======
            "incentivo": incentivo,
            "descuento": descuento,
            "total": total,
            "cantidad_editable": True,
>>>>>>> cd4ef834137816fa7cc26caffef6158c18679788
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


@comercio_requerido
def seguimiento_entregas(request):
    entregas = Entrega.objects.select_related("pedido", "ruta").filter(
        pedido__comercio=request.comercio_actual
    ).order_by("-fecha_estimada")
    return render(request, "plataforma/entregas.html", {"entregas": entregas})


@comercio_requerido
def confirmar_entrega(request, entrega_id):
    entrega = get_object_or_404(
        Entrega.objects.select_related("pedido", "ruta"),
        id=entrega_id,
        pedido__comercio=request.comercio_actual,
    )
    form = EntregaConfirmacionForm(request.POST or None, instance=entrega)
    if request.method == "POST" and form.is_valid():
        entrega = form.save(commit=False)
        entrega.fecha_real = timezone.now()
        entrega.save()
        messages.success(request, "Entrega confirmada correctamente.")
        return redirect("entregas")
    return render(
        request,
        "plataforma/confirmar_entrega.html",
        {
            "form": form,
            "entrega": entrega,
        },
    )


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
