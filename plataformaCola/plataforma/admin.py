from django import forms
from django.contrib import admin

# Importar las clases del modelo
from plataforma.models import (
    Comercio, Incentivo, Usuario, Producto, Pedido,
    Ruta, Notificacion, DetallePedido, Entrega,
    PlantillaIncentivo, ReglaCategoria, ReglaFrecuencia,
    PuntosFidelidad, MovimientoPuntos,
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


# --- Sprint 4: Motor de Incentivos ---

class PlantillaIncentivoForm(forms.ModelForm):
    class Meta:
        model = PlantillaIncentivo
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        umbral_min = cleaned.get("umbral_min")
        umbral_max = cleaned.get("umbral_max")
        if umbral_min is not None and umbral_max is not None and umbral_min >= umbral_max:
            raise forms.ValidationError("El umbral minimo debe ser menor al umbral maximo.")
        return cleaned


class PlantillaIncentivoAdmin(admin.ModelAdmin):
    form = PlantillaIncentivoForm
    list_display = ('tipo', 'umbral_min', 'umbral_max', 'descuento_pct', 'activa')
    list_filter = ('activa',)

admin.site.register(PlantillaIncentivo, PlantillaIncentivoAdmin)


class ReglaCategoriaForm(forms.ModelForm):
    class Meta:
        model = ReglaCategoria
        fields = "__all__"

    def clean_volumen_min(self):
        volumen_min = self.cleaned_data["volumen_min"]
        if volumen_min < 0:
            raise forms.ValidationError("El volumen minimo no puede ser negativo.")
        return volumen_min


class ReglaCategoriaAdmin(admin.ModelAdmin):
    form = ReglaCategoriaForm
    list_display = ('categoria', 'volumen_min', 'bono_descuento_pct')
    ordering = ('volumen_min',)

admin.site.register(ReglaCategoria, ReglaCategoriaAdmin)


class ReglaFrecuenciaAdmin(admin.ModelAdmin):
    list_display = ('ventana_dias', 'pedidos_minimos', 'puntos_por_dolar', 'bono_puntos', 'activa')
    list_filter = ('activa',)

admin.site.register(ReglaFrecuencia, ReglaFrecuenciaAdmin)


class PuntosFidelidadAdmin(admin.ModelAdmin):
    list_display = ('comercio', 'puntos', 'actualizado_en')
    raw_id_fields = ('comercio',)

admin.site.register(PuntosFidelidad, PuntosFidelidadAdmin)


class MovimientoPuntosAdmin(admin.ModelAdmin):
    list_display = ('comercio', 'motivo', 'puntos', 'creado_en')
    list_filter = ('motivo',)
    raw_id_fields = ('comercio', 'pedido')

admin.site.register(MovimientoPuntos, MovimientoPuntosAdmin)
