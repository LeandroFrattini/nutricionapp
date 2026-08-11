from django.db import migrations


def agregar(apps, schema_editor):
    Pais = apps.get_model('core', 'Pais')
    Provincia = apps.get_model('core', 'Provincia')
    Ciudad = apps.get_model('core', 'Ciudad')

    argentina, _ = Pais.objects.get_or_create(nombre='Argentina', defaults={'activo': True})
    buenos_aires, _ = Provincia.objects.get_or_create(
        nombre='Buenos Aires', pais=argentina, defaults={'activa': True}
    )
    Ciudad.objects.get_or_create(
        nombre='Punta Alta', provincia=buenos_aires,
        defaults={'pais': argentina, 'activa': True},
    )


def quitar(apps, schema_editor):
    Ciudad = apps.get_model('core', 'Ciudad')
    Ciudad.objects.filter(nombre='Punta Alta', provincia__nombre='Buenos Aires').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0041_franjahoraria_modalidad_turno_modalidad'),
    ]

    operations = [
        migrations.RunPython(agregar, quitar),
    ]
