from django.db import migrations


def actualizar(apps, schema_editor):
    ObraSocial = apps.get_model('core', 'ObraSocial')
    # "Avalian (ex Medifé)" fue un error de carga — Avalian es el nombre
    # nuevo de ACA Salud, no de Medifé. Medifé es una entidad propia,
    # separada, y sigue existiendo con su propio nombre.
    avalian_mal = ObraSocial.objects.filter(nombre='Avalian (ex Medifé)').first()
    if avalian_mal:
        avalian_mal.nombre = 'Medifé'
        avalian_mal.save(update_fields=['nombre'])
    else:
        ObraSocial.objects.get_or_create(nombre='Medifé', defaults={'activa': True})

    aca = ObraSocial.objects.filter(nombre='ACA Salud').first()
    if aca:
        aca.nombre = 'Avalian (ex ACA Salud)'
        aca.save(update_fields=['nombre'])
    else:
        ObraSocial.objects.get_or_create(nombre='Avalian (ex ACA Salud)', defaults={'activa': True})


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0030_nutricionista_oculto'),
    ]

    operations = [
        migrations.RunPython(actualizar, noop),
    ]
