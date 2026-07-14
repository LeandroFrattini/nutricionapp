from django.db import migrations


def normalizar(apps, schema_editor):
    Paciente = apps.get_model('core', 'Paciente')
    from django.contrib.auth.hashers import make_password

    for p in Paciente.objects.exclude(dni=''):
        dni_normalizado = ''.join(c for c in p.dni if c.isdigit())
        if dni_normalizado == p.dni:
            continue
        p.dni = dni_normalizado
        # Si todavia no cambio su contrasena (sigue siendo la de default,
        # que es el propio DNI), la recalculamos para que coincida con el
        # DNI ya normalizado — si ya la cambio, no la tocamos.
        if p.portal_debe_cambiar_password and dni_normalizado:
            p.portal_password = make_password(dni_normalizado)
        p.save(update_fields=['dni', 'portal_password'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [('core', '0033_poblar_provincias_y_ciudades')]
    operations = [migrations.RunPython(normalizar, noop)]
