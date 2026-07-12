from django.db import migrations

PLANTILLAS_INCENTIVO = [
    # Coincide con el ejemplo de main.tex (M4): 5% desde $200, 10% desde $500.
    {"tipo": "Volumen", "umbral_min": 200, "umbral_max": 499.99, "descuento_pct": 5, "activa": True},
    {"tipo": "Volumen", "umbral_min": 500, "umbral_max": 1_000_000, "descuento_pct": 10, "activa": True},
]

REGLAS_CATEGORIA = [
    {
        "categoria": "Estandar",
        "volumen_min": 0,
        "bono_descuento_pct": 0,
        "beneficio_descripcion": "Acceso completo al catalogo y descuentos estandar por volumen.",
    },
    {
        "categoria": "Preferente",
        "volumen_min": 1500,
        "bono_descuento_pct": 2,
        "beneficio_descripcion": "Descuentos adicionales, condiciones de pago extendidas y atencion prioritaria.",
    },
    {
        "categoria": "Estrategico",
        "volumen_min": 5000,
        "bono_descuento_pct": 5,
        "beneficio_descripcion": "Prioridad de entrega, descuentos diferenciados y gestor de cuenta asignado.",
    },
]


def sembrar_datos(apps, schema_editor):
    PlantillaIncentivo = apps.get_model("plataforma", "PlantillaIncentivo")
    ReglaCategoria = apps.get_model("plataforma", "ReglaCategoria")
    ReglaFrecuencia = apps.get_model("plataforma", "ReglaFrecuencia")

    for datos in PLANTILLAS_INCENTIVO:
        PlantillaIncentivo.objects.get_or_create(
            tipo=datos["tipo"],
            umbral_min=datos["umbral_min"],
            umbral_max=datos["umbral_max"],
            defaults={"descuento_pct": datos["descuento_pct"], "activa": datos["activa"]},
        )

    for datos in REGLAS_CATEGORIA:
        ReglaCategoria.objects.get_or_create(
            categoria=datos["categoria"],
            defaults={
                "volumen_min": datos["volumen_min"],
                "bono_descuento_pct": datos["bono_descuento_pct"],
                "beneficio_descripcion": datos["beneficio_descripcion"],
            },
        )

    ReglaFrecuencia.objects.get_or_create(
        activa=True,
        defaults={
            "ventana_dias": 30,
            "pedidos_minimos": 4,
            "puntos_por_dolar": 1,
            "bono_puntos": 50,
        },
    )


def eliminar_datos(apps, schema_editor):
    PlantillaIncentivo = apps.get_model("plataforma", "PlantillaIncentivo")
    ReglaCategoria = apps.get_model("plataforma", "ReglaCategoria")
    ReglaFrecuencia = apps.get_model("plataforma", "ReglaFrecuencia")
    PlantillaIncentivo.objects.all().delete()
    ReglaCategoria.objects.all().delete()
    ReglaFrecuencia.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("plataforma", "0002_plantillaincentivo_reglacategoria_reglafrecuencia_and_more"),
    ]

    operations = [
        migrations.RunPython(sembrar_datos, eliminar_datos),
    ]
