from django.db import migrations

OBRAS_SOCIALES = [
    'OSDE',
    'Swiss Medical',
    'Galeno',
    'Medicus',
    'Omint',
    'Avalian (ex Medifé)',
    'Sancor Salud',
    'Accord Salud',
    'Premedic',
    'Jerárquicos Salud',
    'Hospital Italiano — Plan de Salud',
    'Hospital Alemán — Plan de Salud',
    'CEMIC',
    'PAMI (INSSJP)',
    'IOMA',
    'Unión Personal (UP)',
    'OSECAC (Empleados de Comercio)',
    'OSPRERA (Rural)',
    'OSPAT (Petroleros)',
    'OSDEPYM',
    'OSPeCon (Construir Salud — UOCRA)',
    'Bancarios (OSBA)',
    'UOM (Metalúrgicos)',
    'Camioneros (OSPeCam)',
    'Luis Pasteur',
    'ASE Nacional',
    'ACA Salud',
    'Federada Salud',
    'Prevención Salud',
    'IOSFA (Fuerzas Armadas)',
    'OSPJN (Poder Judicial)',
    'APROSS (Córdoba)',
    'IOSPER (Entre Ríos)',
    'Obra Social de la Ciudad de Buenos Aires (ObSBA)',
    'Particular (sin obra social)',
]


def poblar(apps, schema_editor):
    ObraSocial = apps.get_model('core', 'ObraSocial')
    for nombre in OBRAS_SOCIALES:
        ObraSocial.objects.get_or_create(nombre=nombre, defaults={'activa': True})


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0021_alter_contactointeresado_apellido_and_more'),
    ]

    operations = [
        migrations.RunPython(poblar, noop),
    ]
