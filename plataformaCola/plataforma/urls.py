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
    path("pedido/eliminar/<int:producto_id>/", views.eliminar_producto_carrito, name="eliminar_producto_carrito"),
    path("pedido/actualizar/<int:producto_id>/", views.actualizar_cantidad_carrito, name="actualizar_cantidad_carrito"),
    path("pedidos/", views.historial_pedidos, name="historial"),
    path("pedidos/<int:pedido_id>/", views.pedido_detalle, name="pedido_detalle"),
    path("pedidos/<int:pedido_id>/reordenar/", views.reordenar_pedido, name="reordenar_pedido"),

    path("logistica/pedidos/", views.pedidos_logistica, name="pedidos_logistica"),
    path("logistica/pedidos/<int:pedido_id>/confirmar/", views.confirmar_pedido_logistica, name="confirmar_pedido_logistica"),

    path("administracion/", views.dashboard_administracion, name="dashboard_administracion"),
    path("administracion/reportes/", views.reportes_administracion, name="reportes_administracion"),
    path("administracion/reportes/csv/", views.reportes_administracion_csv, name="reportes_administracion_csv"),
    path("administracion/reportes/pdf/", views.reportes_administracion_pdf, name="reportes_administracion_pdf"),

    path("perfil/", views.perfil_comercio, name="perfil"),
    path("notificaciones/", views.notificaciones, name="notificaciones"),
    path("incentivos/", views.incentivos, name="incentivos"),
    path("reportes/", views.reportes, name="reportes"),
    path("reportes/csv/", views.reportes_csv, name="reportes_csv"),
]
