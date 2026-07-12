"""Motor de incentivos (Sprint 4 / M4): descuentos por volumen, categoria comercial y
bonificacion por frecuencia. Toda la parametrizacion vive en modelos editables desde el
admin (PlantillaIncentivo, ReglaCategoria, ReglaFrecuencia) para cumplir RF-05: el
administrador ajusta umbrales y reglas sin intervencion tecnica.
"""

from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from .models import (
    Incentivo,
    MovimientoPuntos,
    Pedido,
    PlantillaIncentivo,
    PuntosFidelidad,
    ReglaCategoria,
    ReglaFrecuencia,
)

VENTANA_VOLUMEN_DIAS = 90
ESTADOS_EXCLUIDOS_DE_VOLUMEN = ["Cancelado"]


def crear_incentivos_por_defecto(comercio):
    """Copia la plantilla global de descuentos por volumen a un comercio (idempotente)."""
    creados = []
    for plantilla in PlantillaIncentivo.objects.filter(activa=True).order_by("umbral_min"):
        incentivo, _ = Incentivo.objects.get_or_create(
            comercio=comercio,
            tipo=plantilla.tipo,
            umbral_min=plantilla.umbral_min,
            umbral_max=plantilla.umbral_max,
            defaults={"descuento_pct": plantilla.descuento_pct, "activo": True},
        )
        creados.append(incentivo)
    return creados


def calcular_descuento_pedido(comercio, subtotal):
    """Descuento total de un pedido: mejor tramo de volumen vigente + bono de la categoria actual."""
    incentivo = (
        Incentivo.objects.filter(
            comercio=comercio,
            activo=True,
            umbral_min__lte=subtotal,
            umbral_max__gte=subtotal,
        )
        .order_by("-descuento_pct")
        .first()
    )
    descuento_volumen_pct = incentivo.descuento_pct if incentivo else 0

    regla_categoria = ReglaCategoria.objects.filter(categoria=comercio.categoria).first()
    bono_categoria_pct = regla_categoria.bono_descuento_pct if regla_categoria else 0

    descuento_pct_total = descuento_volumen_pct + bono_categoria_pct
    descuento_monto = round(subtotal * (descuento_pct_total / 100), 2)

    return {
        "incentivo": incentivo,
        "descuento_volumen_pct": descuento_volumen_pct,
        "bono_categoria_pct": bono_categoria_pct,
        "descuento_pct_total": descuento_pct_total,
        "descuento": descuento_monto,
        "total": round(subtotal - descuento_monto, 2),
    }


def recalcular_categoria(comercio):
    """Recalcula volumen_90d y la categoria comercial (puede subir o bajar de nivel)."""
    desde = timezone.now() - timedelta(days=VENTANA_VOLUMEN_DIAS)
    volumen = (
        Pedido.objects.filter(comercio=comercio, fecha__gte=desde)
        .exclude(estado__in=ESTADOS_EXCLUIDOS_DE_VOLUMEN)
        .aggregate(total=Sum("monto_total"))["total"]
        or 0
    )

    regla = ReglaCategoria.objects.filter(volumen_min__lte=volumen).order_by("-volumen_min").first()

    categoria_anterior = comercio.categoria
    comercio.volumen_90d = volumen
    if regla:
        comercio.categoria = regla.categoria
    comercio.save(update_fields=["volumen_90d", "categoria"])
    return categoria_anterior, comercio.categoria


def evaluar_bonificacion_frecuencia(comercio, pedido):
    """Otorga puntos por la compra y, si corresponde, el bono por frecuencia de pedidos."""
    regla = ReglaFrecuencia.objects.filter(activa=True).order_by("-id").first()
    cuenta, _ = PuntosFidelidad.objects.get_or_create(comercio=comercio)

    if not regla:
        return cuenta

    puntos_compra = int(pedido.monto_total * regla.puntos_por_dolar)
    if puntos_compra > 0:
        MovimientoPuntos.objects.create(
            comercio=comercio,
            pedido=pedido,
            puntos=puntos_compra,
            motivo="Compra",
        )

    desde = timezone.now() - timedelta(days=regla.ventana_dias)
    pedidos_en_ventana = (
        Pedido.objects.filter(comercio=comercio, fecha__gte=desde)
        .exclude(estado__in=ESTADOS_EXCLUIDOS_DE_VOLUMEN)
        .count()
    )
    bono_ya_otorgado = MovimientoPuntos.objects.filter(
        comercio=comercio, motivo="Frecuencia", creado_en__gte=desde
    ).exists()

    if pedidos_en_ventana >= regla.pedidos_minimos and not bono_ya_otorgado and regla.bono_puntos > 0:
        MovimientoPuntos.objects.create(
            comercio=comercio,
            pedido=pedido,
            puntos=regla.bono_puntos,
            motivo="Frecuencia",
        )

    cuenta.puntos = MovimientoPuntos.objects.filter(comercio=comercio).aggregate(total=Sum("puntos"))["total"] or 0
    cuenta.save(update_fields=["puntos"])
    return cuenta


def siguiente_categoria(comercio):
    """Devuelve (regla_siguiente, volumen_faltante) para motivar al comercio a subir de nivel."""
    regla = (
        ReglaCategoria.objects.filter(volumen_min__gt=comercio.volumen_90d)
        .order_by("volumen_min")
        .first()
    )
    if not regla:
        return None, None
    return regla, round(regla.volumen_min - comercio.volumen_90d, 2)
