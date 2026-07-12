from django.core.management.base import BaseCommand

from plataforma.incentivos import crear_incentivos_por_defecto, recalcular_categoria
from plataforma.models import Comercio


class Command(BaseCommand):
    help = (
        "Aplica la plantilla de descuentos por volumen a comercios sin incentivos y "
        "recalcula la categoria comercial de todos los comercios (cierre de ciclo de 90 dias)."
    )

    def handle(self, *args, **options):
        comercios = Comercio.objects.all()
        for comercio in comercios:
            creados = crear_incentivos_por_defecto(comercio)
            categoria_anterior, categoria_nueva = recalcular_categoria(comercio)
            self.stdout.write(
                "%s: %s incentivo(s) verificados, categoria %s -> %s"
                % (comercio.nombre_comercial, len(creados), categoria_anterior, categoria_nueva)
            )
        self.stdout.write(self.style.SUCCESS("Proceso completado para %s comercio(s)." % comercios.count()))
