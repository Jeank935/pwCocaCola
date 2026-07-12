from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("registro/", views.registro, name="registro"),
    path("login/", views.iniciar_sesion, name="login"),
    path("logout/", views.cerrar_sesion, name="logout"),

    path("catalogo/", views.catalogo, name="catalogo"),
    path("catalogo/agregar/<int:producto_id>/", views.agregar_producto, name="agregar_producto"),

    path("pedido/paso-1/", views.pedido_paso1, name="pedido_paso1"),
    path("pedido/paso-2/", views.pedido_paso2, name="pedido_paso2"),
    path("pedido/paso-3/", views.pedido_paso3, name="pedido_paso3"),

    path("pedido/limpiar/", views.carrito_limpiar, name="carrito_limpiar"),
    path("pedidos/", views.historial_pedidos, name="historial"),
    path("pedidos/<int:pedido_id>/", views.pedido_detalle, name="pedido_detalle"),
    path("pedidos/<int:pedido_id>/reordenar/", views.reordenar_pedido, name="reordenar_pedido"),

    path("perfil/", views.perfil_comercio, name="perfil"),
    path("notificaciones/", views.notificaciones, name="notificaciones"),
    path("incentivos/", views.incentivos, name="incentivos"),
    path("entregas/", views.seguimiento_entregas, name="entregas"),
    path("entregas/<int:entrega_id>/confirmar/", views.confirmar_entrega, name="confirmar_entrega"),

    path("reportes/", views.reportes, name="reportes"),
    path("reportes/csv/", views.reportes_csv, name="reportes_csv"),
]
