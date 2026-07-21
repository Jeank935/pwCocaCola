# ISBEN Solution

Plataforma web B2B desarrollada con Django para gestionar comercios, productos, pedidos, incentivos, logística y reportes.
  
## Instalación y ejecución

```powershell
cd plataformaCola
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Abra `http://127.0.0.1:8000/` en el navegador.

## Usuarios

Un usuario de Comercio puede registrarse en:

```text
http://127.0.0.1:8000/registro/
```

Para administrar datos y crear usuarios de Logística o Administración, cree primero un superusuario:

```powershell
python manage.py createsuperuser
```

