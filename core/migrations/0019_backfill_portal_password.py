from django.db import migrations


def backfill_portal_password(apps, schema_editor):
    from django.contrib.auth.hashers import make_password
    Paciente = apps.get_model('core', 'Paciente')
    for p in Paciente.objects.exclude(dni='').filter(portal_password=''):
        p.portal_password = make_password(p.dni)
        p.save(update_fields=['portal_password'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0018_paciente_portal_debe_cambiar_password_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_portal_password, noop),
    ]
