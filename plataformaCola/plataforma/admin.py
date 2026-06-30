from django.contrib import admin

# Importar las clases del modelo
from plataforma.models import (
    Comercio, Incentivo, Usuario, Producto, Pedido, 
    Ruta, Notificacion, DetallePedido, Entrega
)

# Se crea una clase que hereda
# de ModelAdmin para el modelo
# Comercio
class ComercioAdmin(admin.ModelAdmin):
    list_display = ('ruc', 'nombre_comercial', 'categoria', 'estado')
    search_fields = ('ruc', 'nombre_comercial')

admin.site.register(Comercio, ComercioAdmin)


class IncentivoAdmin(admin.ModelAdmin):
    list_display = ('tipo', 'comercio', 'activo')
    raw_id_fields = ('comercio',)

admin.site.register(Incentivo, IncentivoAdmin)


class UsuarioAdmin(admin.ModelAdmin):
    list_display = ('email', 'rol', 'comercio')
    search_fields = ('email', 'rol')
    raw_id_fields = ('comercio',)

admin.site.register(Usuario, UsuarioAdmin)


class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'precio', 'stock', 'activo')
    search_fields = ('nombre',)

admin.site.register(Producto, ProductoAdmin)


class PedidoAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'estado', 'monto_total', 'comercio', 'usuario')
    search_fields = ('estado',)
    raw_id_fields = ('comercio', 'usuario')

admin.site.register(Pedido, PedidoAdmin)


class RutaAdmin(admin.ModelAdmin):
    list_display = ('zona', 'vehiculo', 'capacidad_max')
    search_fields = ('zona', 'vehiculo')

admin.site.register(Ruta, RutaAdmin)


class NotificacionAdmin(admin.ModelAdmin):
    list_display = ('canal', 'enviado_en', 'comercio', 'pedido')
    raw_id_fields = ('comercio', 'pedido')

admin.site.register(Notificacion, NotificacionAdmin)


class DetallePedidoAdmin(admin.ModelAdmin):
    list_display = ('cantidad', 'subtotal', 'pedido', 'producto')
    raw_id_fields = ('pedido', 'producto')

admin.site.register(DetallePedido, DetallePedidoAdmin)


class EntregaAdmin(admin.ModelAdmin):
    list_display = ('fecha_estimada', 'tipo_confirmacion', 'pedido', 'ruta')
    raw_id_fields = ('pedido', 'ruta')

admin.site.register(Entrega, EntregaAdmin)
