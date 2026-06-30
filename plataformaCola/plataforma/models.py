from django.db import models

# Create your models here.

class Comercio(models.Model):
    ruc = models.CharField(max_length=20)
    nombre_comercial = models.CharField(max_length=100)
    direccion = models.CharField(max_length=255)
    contacto = models.CharField(max_length=100)
    categoria = models.CharField(max_length=100)
    volumen_90d = models.FloatField()
    estado = models.CharField(max_length=50)

    def __str__(self):
        return "%s %s" % (self.ruc, self.nombre_comercial)

class Incentivo(models.Model):
    tipo = models.CharField(max_length=100)
    umbral_min = models.FloatField()
    umbral_max = models.FloatField()
    descuento_pct = models.FloatField()
    activo = models.BooleanField(default=True)
    comercio = models.ForeignKey(Comercio, on_delete=models.CASCADE, 
    related_name="incentivos")

    def __str__(self):
        return "%s %s" % (self.tipo, self.activo)

class Usuario(models.Model):
    email = models.CharField(max_length=100)
    password_hash = models.CharField(max_length=255)
    rol = models.CharField(max_length=50)
    ultima_sesion = models.DateTimeField()
    comercio = models.ForeignKey(Comercio, on_delete=models.CASCADE, 
    related_name="usuarios")

    def __str__(self):
        return "%s %s" % (self.email, self.rol)

class Producto(models.Model):
    nombre = models.CharField(max_length=100)
    precio = models.FloatField()
    stock = models.IntegerField()
    activo = models.BooleanField(default=True)
    imagen_url = models.CharField(max_length=255)

    def __str__(self):
        return "%s %s" % (self.nombre, self.precio)

class Pedido(models.Model):
    fecha = models.DateTimeField()
    estado = models.CharField(max_length=50)
    monto_total = models.FloatField()
    descuento = models.FloatField()
    sincronizado = models.BooleanField(default=False)
    comercio = models.ForeignKey(Comercio, on_delete=models.CASCADE, 
    related_name="pedidos")
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, 
    related_name="pedidos")

    def __str__(self):
        return "%s %s" % (self.fecha, self.estado)

class Ruta(models.Model):
    zona = models.CharField(max_length=100)
    capacidad_max = models.IntegerField()
    vehiculo = models.CharField(max_length=100)

    def __str__(self):
        return "%s %s" % (self.zona, self.vehiculo)

class Notificacion(models.Model):
    canal = models.CharField(max_length=50)
    mensaje = models.CharField(max_length=255)
    enviado_en = models.DateTimeField()
    comercio = models.ForeignKey(Comercio, on_delete=models.CASCADE, 
    related_name="notificaciones")
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, 
    related_name="notificaciones")

    def __str__(self):
        return "%s %s" % (self.canal, self.enviado_en)

class DetallePedido(models.Model):
    cantidad = models.IntegerField()
    precio_unitario = models.FloatField()
    subtotal = models.FloatField()
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, 
    related_name="detalles")
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, 
    related_name="detalles")

    def __str__(self):
        return "%s %s" % (self.cantidad, self.subtotal)

class Entrega(models.Model):
    fecha_estimada = models.DateTimeField()
    fecha_real = models.DateTimeField(null=True, blank=True)
    tipo_confirmacion = models.CharField(max_length=50)
    evidencia_url = models.CharField(max_length=255, null=True, blank=True)
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE,
     related_name="entregas")
    ruta = models.ForeignKey(Ruta, on_delete=models.CASCADE,
     related_name="entregas")

    def __str__(self):
        return "%s %s" % (self.fecha_estimada, self.tipo_confirmacion)
