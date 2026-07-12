from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.test import Client, TestCase
from django.utils import timezone

from .incentivos import (
    calcular_descuento_pedido,
    crear_incentivos_por_defecto,
    evaluar_bonificacion_frecuencia,
    recalcular_categoria,
)
from .models import (
    Comercio,
    Incentivo,
    MovimientoPuntos,
    Pedido,
    PlantillaIncentivo,
    Producto,
    PuntosFidelidad,
    ReglaCategoria,
    ReglaFrecuencia,
    Ruta,
    Usuario,
)


def crear_comercio(ruc="1790000000001", categoria="Estandar", volumen_90d=0):
    return Comercio.objects.create(
        ruc=ruc,
        nombre_comercial="Tienda Test",
        direccion="Av. Siempre Viva 123",
        contacto="Juan Perez",
        categoria=categoria,
        volumen_90d=volumen_90d,
        estado="Activo",
    )


def crear_usuario(comercio, email="test@example.com"):
    return Usuario.objects.create(
        email=email,
        password_hash=make_password("abc12345"),
        rol="Comercio",
        ultima_sesion=timezone.now(),
        comercio=comercio,
    )


class PlantillasYReglasSemillaTests(TestCase):
    """La migracion de datos debe dejar el motor de incentivos listo para usarse sin admin."""

    def test_plantillas_de_volumen_sembradas(self):
        self.assertEqual(PlantillaIncentivo.objects.filter(activa=True).count(), 2)
        tramo_5 = PlantillaIncentivo.objects.get(descuento_pct=5)
        self.assertEqual(tramo_5.umbral_min, 200)
        tramo_10 = PlantillaIncentivo.objects.get(descuento_pct=10)
        self.assertEqual(tramo_10.umbral_min, 500)

    def test_reglas_de_categoria_sembradas(self):
        self.assertEqual(ReglaCategoria.objects.count(), 3)
        self.assertTrue(ReglaCategoria.objects.filter(categoria="Estandar", volumen_min=0).exists())
        self.assertTrue(ReglaCategoria.objects.filter(categoria="Preferente").exists())
        self.assertTrue(ReglaCategoria.objects.filter(categoria="Estrategico").exists())

    def test_regla_de_frecuencia_sembrada(self):
        self.assertTrue(ReglaFrecuencia.objects.filter(activa=True).exists())


class CrearIncentivosPorDefectoTests(TestCase):
    def test_copia_la_plantilla_al_comercio_nuevo(self):
        comercio = crear_comercio()
        creados = crear_incentivos_por_defecto(comercio)
        activas = PlantillaIncentivo.objects.filter(activa=True).count()
        self.assertEqual(len(creados), activas)
        self.assertEqual(Incentivo.objects.filter(comercio=comercio).count(), activas)

    def test_es_idempotente_no_duplica_incentivos(self):
        comercio = crear_comercio()
        crear_incentivos_por_defecto(comercio)
        crear_incentivos_por_defecto(comercio)
        activas = PlantillaIncentivo.objects.filter(activa=True).count()
        self.assertEqual(Incentivo.objects.filter(comercio=comercio).count(), activas)


class CalculoDescuentoTests(TestCase):
    def setUp(self):
        self.comercio = crear_comercio()
        crear_incentivos_por_defecto(self.comercio)

    def test_sin_alcanzar_ningun_tramo_no_hay_descuento(self):
        calculo = calcular_descuento_pedido(self.comercio, 50)
        self.assertEqual(calculo["descuento_volumen_pct"], 0)
        self.assertEqual(calculo["descuento"], 0)
        self.assertEqual(calculo["total"], 50)

    def test_tramo_200_aplica_5_por_ciento(self):
        calculo = calcular_descuento_pedido(self.comercio, 300)
        self.assertEqual(calculo["descuento_volumen_pct"], 5)
        self.assertEqual(calculo["descuento"], 15)
        self.assertEqual(calculo["total"], 285)

    def test_tramo_500_aplica_10_por_ciento(self):
        calculo = calcular_descuento_pedido(self.comercio, 1000)
        self.assertEqual(calculo["descuento_volumen_pct"], 10)
        self.assertEqual(calculo["descuento"], 100)
        self.assertEqual(calculo["total"], 900)

    def test_categoria_preferente_suma_su_bono_al_descuento_de_volumen(self):
        self.comercio.categoria = "Preferente"
        self.comercio.save(update_fields=["categoria"])
        regla = ReglaCategoria.objects.get(categoria="Preferente")

        calculo = calcular_descuento_pedido(self.comercio, 300)

        self.assertEqual(calculo["bono_categoria_pct"], regla.bono_descuento_pct)
        self.assertEqual(calculo["descuento_pct_total"], 5 + regla.bono_descuento_pct)
        self.assertEqual(calculo["descuento"], round(300 * calculo["descuento_pct_total"] / 100, 2))


class RecalculoCategoriaTests(TestCase):
    def setUp(self):
        self.comercio = crear_comercio()
        self.usuario = crear_usuario(self.comercio)

    def _crear_pedido(self, monto, dias_atras=0, estado="Confirmado"):
        return Pedido.objects.create(
            fecha=timezone.now() - timedelta(days=dias_atras),
            estado=estado,
            monto_total=monto,
            descuento=0,
            sincronizado=True,
            comercio=self.comercio,
            usuario=self.usuario,
        )

    def test_sube_a_preferente_al_superar_el_umbral_de_volumen_90d(self):
        umbral = ReglaCategoria.objects.get(categoria="Preferente").volumen_min
        self._crear_pedido(umbral + 1)

        _, categoria_nueva = recalcular_categoria(self.comercio)

        self.assertEqual(categoria_nueva, "Preferente")
        self.comercio.refresh_from_db()
        self.assertEqual(self.comercio.volumen_90d, umbral + 1)

    def test_sube_a_estrategico_al_superar_su_umbral(self):
        umbral = ReglaCategoria.objects.get(categoria="Estrategico").volumen_min
        self._crear_pedido(umbral + 500)

        _, categoria_nueva = recalcular_categoria(self.comercio)

        self.assertEqual(categoria_nueva, "Estrategico")

    def test_baja_de_categoria_si_el_volumen_queda_fuera_de_la_ventana_de_90_dias(self):
        umbral = ReglaCategoria.objects.get(categoria="Preferente").volumen_min
        self._crear_pedido(umbral + 1, dias_atras=120)

        _, categoria_nueva = recalcular_categoria(self.comercio)

        self.assertEqual(categoria_nueva, "Estandar")

    def test_pedidos_cancelados_no_cuentan_para_el_volumen(self):
        umbral = ReglaCategoria.objects.get(categoria="Preferente").volumen_min
        self._crear_pedido(umbral + 1, estado="Cancelado")

        _, categoria_nueva = recalcular_categoria(self.comercio)

        self.assertEqual(categoria_nueva, "Estandar")


class BonificacionFrecuenciaTests(TestCase):
    def setUp(self):
        self.comercio = crear_comercio()
        self.usuario = crear_usuario(self.comercio)
        self.regla = ReglaFrecuencia.objects.filter(activa=True).first()

    def _crear_pedido(self, monto=100):
        return Pedido.objects.create(
            fecha=timezone.now(),
            estado="Confirmado",
            monto_total=monto,
            descuento=0,
            sincronizado=True,
            comercio=self.comercio,
            usuario=self.usuario,
        )

    def test_otorga_puntos_por_compra_segun_la_regla_activa(self):
        pedido = self._crear_pedido(100)
        cuenta = evaluar_bonificacion_frecuencia(self.comercio, pedido)
        self.assertEqual(cuenta.puntos, int(100 * self.regla.puntos_por_dolar))

    def test_bono_de_frecuencia_se_otorga_solo_una_vez_por_ventana(self):
        for _ in range(self.regla.pedidos_minimos):
            pedido = self._crear_pedido(10)
            evaluar_bonificacion_frecuencia(self.comercio, pedido)

        bonos = MovimientoPuntos.objects.filter(comercio=self.comercio, motivo="Frecuencia").count()
        self.assertEqual(bonos, 1)

        pedido_extra = self._crear_pedido(10)
        evaluar_bonificacion_frecuencia(self.comercio, pedido_extra)
        bonos_despues = MovimientoPuntos.objects.filter(comercio=self.comercio, motivo="Frecuencia").count()
        self.assertEqual(bonos_despues, 1)

    def test_no_otorga_bono_de_frecuencia_si_no_alcanza_el_minimo_de_pedidos(self):
        for _ in range(self.regla.pedidos_minimos - 1):
            pedido = self._crear_pedido(10)
            evaluar_bonificacion_frecuencia(self.comercio, pedido)

        bonos = MovimientoPuntos.objects.filter(comercio=self.comercio, motivo="Frecuencia").count()
        self.assertEqual(bonos, 0)


class FlujoPedidoIntegracionTests(TestCase):
    """Verifica el flujo real via HTTP: registro -> catalogo -> checkout -> incentivos aplicados."""

    def setUp(self):
        self.client = Client()
        Ruta.objects.create(zona="Norte", capacidad_max=50, vehiculo="Camion")
        self.producto = Producto.objects.create(
            nombre="Coca-Cola 350ml", precio=0.75, stock=1000, activo=True, imagen_url=""
        )

    def _registrar(self, ruc, email):
        return self.client.post(
            "/registro/",
            {
                "ruc": ruc,
                "nombre_comercial": "Tienda Integracion",
                "direccion": "Calle Falsa 123",
                "contacto": "Ana Lopez",
                "email": email,
                "password": "abc12345",
            },
            follow=True,
        )

    def test_registro_siembra_incentivos_por_defecto(self):
        self._registrar("1790000000099", "integracion@example.com")
        comercio = Comercio.objects.get(ruc="1790000000099")
        activas = PlantillaIncentivo.objects.filter(activa=True).count()
        self.assertEqual(Incentivo.objects.filter(comercio=comercio).count(), activas)

    def test_flujo_completo_de_pedido_actualiza_categoria_y_otorga_puntos(self):
        self._registrar("1790000000098", "flujo@example.com")
        comercio = Comercio.objects.get(ruc="1790000000098")

        self.client.post("/catalogo/agregar/%s/" % self.producto.id, {"cantidad": 800})
        respuesta = self.client.post("/pedido/paso-3/", {}, follow=True)
        self.assertEqual(respuesta.status_code, 200)

        pedido = Pedido.objects.get(comercio=comercio)
        # 800 unidades x $0.75 = $600 subtotal -> tramo del 10% (>= $500)
        self.assertAlmostEqual(pedido.descuento, 60.0, places=2)
        self.assertAlmostEqual(pedido.monto_total, 540.0, places=2)

        comercio.refresh_from_db()
        self.assertEqual(comercio.volumen_90d, 540.0)

        cuenta = PuntosFidelidad.objects.get(comercio=comercio)
        self.assertGreater(cuenta.puntos, 0)

    def test_stock_se_descuenta_y_pedido_queda_dentro_de_una_transaccion(self):
        self._registrar("1790000000097", "stock@example.com")
        self.client.post("/catalogo/agregar/%s/" % self.producto.id, {"cantidad": 10})
        self.client.post("/pedido/paso-3/", {}, follow=True)

        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 990)
