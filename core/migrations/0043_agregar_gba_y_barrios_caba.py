from django.db import migrations

# Partidos del Gran Buenos Aires que todavia no estaban cargados (algunos
# del primer y segundo cordon ya venian de la migracion 0033: Lomas de
# Zamora, Moron, Pilar, Quilmes, San Isidro, Tigre, Vicente Lopez, Escobar,
# Campana, Zarate, Lujan).
PARTIDOS_GBA = [
    'Almirante Brown', 'Avellaneda', 'Berazategui', 'Esteban Echeverría',
    'Ezeiza', 'Florencio Varela', 'General San Martín', 'Hurlingham',
    'Ituzaingó', 'José C. Paz', 'La Matanza', 'Lanús', 'Malvinas Argentinas',
    'Merlo', 'Moreno', 'San Fernando', 'San Miguel', 'Tres de Febrero',
    'San Vicente', 'Presidente Perón', 'Marcos Paz', 'Cañuelas', 'General Rodríguez',
]

# Los 48 barrios oficiales de CABA (agrupados en 15 comunas) — se cargan
# como Ciudad aparte, bajo la misma provincia "Ciudad Autónoma de Buenos
# Aires" que ya tiene la entrada genérica (que se deja tal cual, para no
# romper a los nutricionistas que ya la tuvieran elegida).
BARRIOS_CABA = [
    'Retiro', 'San Nicolás', 'Puerto Madero', 'San Telmo', 'Montserrat', 'Constitución',
    'Recoleta',
    'Balvanera', 'San Cristóbal',
    'La Boca', 'Barracas', 'Parque Patricios', 'Nueva Pompeya',
    'Almagro', 'Boedo',
    'Caballito',
    'Flores', 'Parque Chacabuco',
    'Villa Soldati', 'Villa Riachuelo', 'Villa Lugano',
    'Liniers', 'Mataderos', 'Parque Avellaneda',
    'Versalles', 'Monte Castro', 'Villa Real', 'Floresta', 'Vélez Sarsfield', 'Villa Luro',
    'Villa General Mitre', 'Villa Devoto', 'Villa del Parque', 'Villa Santa Rita',
    'Coghlan', 'Saavedra', 'Villa Urquiza', 'Villa Pueyrredón',
    'Núñez', 'Belgrano', 'Colegiales',
    'Palermo',
    'Chacarita', 'Villa Crespo', 'La Paternal', 'Villa Ortúzar', 'Agronomía', 'Parque Chas',
]


def agregar(apps, schema_editor):
    Pais = apps.get_model('core', 'Pais')
    Provincia = apps.get_model('core', 'Provincia')
    Ciudad = apps.get_model('core', 'Ciudad')

    argentina, _ = Pais.objects.get_or_create(nombre='Argentina', defaults={'activo': True})

    buenos_aires, _ = Provincia.objects.get_or_create(
        nombre='Buenos Aires', pais=argentina, defaults={'activa': True}
    )
    for nombre in PARTIDOS_GBA:
        Ciudad.objects.get_or_create(
            nombre=nombre, provincia=buenos_aires,
            defaults={'pais': argentina, 'activa': True},
        )

    caba, _ = Provincia.objects.get_or_create(
        nombre='Ciudad Autónoma de Buenos Aires', pais=argentina, defaults={'activa': True}
    )
    for nombre in BARRIOS_CABA:
        Ciudad.objects.get_or_create(
            nombre=nombre, provincia=caba,
            defaults={'pais': argentina, 'activa': True},
        )


def quitar(apps, schema_editor):
    Ciudad = apps.get_model('core', 'Ciudad')
    Ciudad.objects.filter(nombre__in=PARTIDOS_GBA, provincia__nombre='Buenos Aires').delete()
    Ciudad.objects.filter(nombre__in=BARRIOS_CABA, provincia__nombre='Ciudad Autónoma de Buenos Aires').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0042_agregar_ciudad_punta_alta'),
    ]

    operations = [
        migrations.RunPython(agregar, quitar),
    ]
