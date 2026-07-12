from django.db import migrations


def desasociar_usuarios_operativos(apps, schema_editor):
    Usuario = apps.get_model("plataforma", "Usuario")
    Usuario.objects.filter(rol__iexact="Logistica").update(comercio=None)
    Usuario.objects.filter(rol__iexact="Administrador").update(comercio=None)


class Migration(migrations.Migration):

    dependencies = [
        ("plataforma", "0004_alter_usuario_comercio"),
    ]

    operations = [
        migrations.RunPython(desasociar_usuarios_operativos, migrations.RunPython.noop),
    ]
