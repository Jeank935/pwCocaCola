from django import forms
from django.contrib.auth.hashers import make_password
from django.utils import timezone

from .incentivos import crear_incentivos_por_defecto
from .models import Comercio, Pedido, Ruta, Usuario


class RegistroComercioForm(forms.Form):
    ruc = forms.CharField(max_length=20, label="RUC")
    nombre_comercial = forms.CharField(max_length=100, label="Nombre comercial")
    direccion = forms.CharField(max_length=255, label="Direccion")
    contacto = forms.CharField(max_length=100, label="Contacto")
    email = forms.EmailField(max_length=100, label="Correo electronico")
    password = forms.CharField(
        min_length=6,
        label="Contrasena",
        widget=forms.PasswordInput,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean_ruc(self):
        ruc = self.cleaned_data["ruc"].strip()
        if Comercio.objects.filter(ruc=ruc).exists():
            raise forms.ValidationError("Ya existe un comercio registrado con este RUC.")
        return ruc

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if Usuario.objects.filter(email=email).exists():
            raise forms.ValidationError("Ya existe un usuario registrado con este correo.")
        return email

    def save(self):
        comercio = Comercio.objects.create(
            ruc=self.cleaned_data["ruc"],
            nombre_comercial=self.cleaned_data["nombre_comercial"],
            direccion=self.cleaned_data["direccion"],
            contacto=self.cleaned_data["contacto"],
            categoria="Estandar",
            volumen_90d=0,
            estado="Activo",
        )
        usuario = Usuario.objects.create(
            email=self.cleaned_data["email"],
            password_hash=make_password(self.cleaned_data["password"]),
            rol="Comercio",
            ultima_sesion=timezone.now(),
            comercio=comercio,
        )
        crear_incentivos_por_defecto(comercio)
        return usuario


class LoginForm(forms.Form):
    email = forms.EmailField(max_length=100, label="Correo electronico")
    password = forms.CharField(label="Contrasena", widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class ComercioForm(forms.ModelForm):
    class Meta:
        model = Comercio
        fields = ["nombre_comercial", "direccion", "contacto"]
        labels = {
            "nombre_comercial": "Nombre comercial",
            "direccion": "Direccion",
            "contacto": "Contacto",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class ReporteFiltroForm(forms.Form):
    estado = forms.CharField(max_length=50, required=False, label="Estado")
    fecha_desde = forms.DateField(
        required=False,
        label="Desde",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    fecha_hasta = forms.DateField(
        required=False,
        label="Hasta",
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class ReporteAdministrativoFiltroForm(forms.Form):
    zona = forms.ChoiceField(required=False, label="Zona")
    fecha_desde = forms.DateField(
        required=False,
        label="Desde",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    fecha_hasta = forms.DateField(
        required=False,
        label="Hasta",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    estado = forms.ChoiceField(required=False, label="Estado")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        zonas = Ruta.objects.order_by("zona").values_list("zona", flat=True).distinct()
        estados = Pedido.objects.order_by("estado").values_list("estado", flat=True).distinct()
        self.fields["zona"].choices = [("", "Todas")] + [(zona, zona) for zona in zonas]
        self.fields["estado"].choices = [("", "Todos")] + [
            (estado, estado) for estado in estados
        ]
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned_data = super().clean()
        fecha_desde = cleaned_data.get("fecha_desde")
        fecha_hasta = cleaned_data.get("fecha_hasta")
        if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
            raise forms.ValidationError("La fecha inicial no puede superar la fecha final.")
        return cleaned_data
