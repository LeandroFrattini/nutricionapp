from django.db import migrations

# Provincia -> lista de ciudades principales. No es exhaustivo (no incluye
# cada localidad chica del país), pero cubre las capitales y ciudades más
# grandes/conocidas de cada provincia — suficiente para que un nutricionista
# encuentre la suya sin tener que pedir que se cargue a mano.
PROVINCIAS_Y_CIUDADES = {
    'Ciudad Autónoma de Buenos Aires': [
        'Ciudad Autónoma de Buenos Aires',
    ],
    'Buenos Aires': [
        'La Plata', 'Mar del Plata', 'Bahía Blanca', 'Tandil', 'Quilmes',
        'Lomas de Zamora', 'San Isidro', 'Vicente López', 'Morón', 'San Justo',
        'Tigre', 'Pilar', 'Escobar', 'Zárate', 'Campana', 'Luján', 'Chascomús',
        'Necochea', 'Olavarría', 'Azul', 'Junín', 'Pergamino', 'San Nicolás de los Arroyos',
    ],
    'Catamarca': [
        'San Fernando del Valle de Catamarca', 'Andalgalá', 'Belén', 'Recreo', 'Tinogasta', 'Santa María',
    ],
    'Chaco': [
        'Resistencia', 'Presidencia Roque Sáenz Peña', 'Villa Ángela', 'Charata', 'Machagai', 'General San Martín', 'Barranqueras',
    ],
    'Chubut': [
        'Rawson', 'Comodoro Rivadavia', 'Trelew', 'Puerto Madryn', 'Esquel', 'Trevelin', 'Gaiman',
    ],
    'Córdoba': [
        'Córdoba', 'Villa Carlos Paz', 'Río Cuarto', 'Villa María', 'San Francisco',
        'Alta Gracia', 'Jesús María', 'Bell Ville', 'Cosquín', 'La Falda', 'Marcos Juárez', 'Río Tercero',
    ],
    'Corrientes': [
        'Corrientes', 'Goya', 'Mercedes', 'Paso de los Libres', 'Curuzú Cuatiá', 'Santo Tomé', 'Bella Vista',
    ],
    'Entre Ríos': [
        'Paraná', 'Concordia', 'Gualeguaychú', 'Gualeguay', 'Concepción del Uruguay', 'Villaguay', 'Colón', 'Nogoyá',
    ],
    'Formosa': [
        'Formosa', 'Clorinda', 'Pirané', 'El Colorado', 'Las Lomitas',
    ],
    'Jujuy': [
        'San Salvador de Jujuy', 'Palpalá', 'Perico', 'Libertador General San Martín',
        'San Pedro de Jujuy', 'Humahuaca', 'Tilcara',
    ],
    'La Pampa': [
        'Santa Rosa', 'General Pico', 'Toay', 'Realicó', 'General Acha',
    ],
    'La Rioja': [
        'La Rioja', 'Chilecito', 'Aimogasta', 'Chamical', 'Villa Unión',
    ],
    'Mendoza': [
        'Mendoza', 'San Rafael', 'Godoy Cruz', 'Guaymallén', 'Las Heras',
        'Maipú', 'Luján de Cuyo', 'General Alvear', 'Tunuyán', 'Malargüe',
    ],
    'Misiones': [
        'Posadas', 'Oberá', 'Eldorado', 'Puerto Iguazú', 'Puerto Rico', 'Leandro N. Alem', 'San Vicente', 'Apóstoles',
    ],
    'Neuquén': [
        'Neuquén', 'San Martín de los Andes', 'Villa La Angostura', 'Cutral Có', 'Zapala', 'Plottier', 'Centenario', 'Plaza Huincul',
    ],
    'Río Negro': [
        'Viedma', 'San Carlos de Bariloche', 'General Roca', 'Cipolletti', 'Villa Regina', 'El Bolsón', 'Choele Choel',
    ],
    'Salta': [
        'Salta', 'San Ramón de la Nueva Orán', 'Tartagal', 'Cafayate', 'Metán', 'Rosario de la Frontera', 'Güemes',
    ],
    'San Juan': [
        'San Juan', 'Rawson', 'Chimbas', 'Rivadavia', 'Pocito', 'Caucete', 'Jáchal',
    ],
    'San Luis': [
        'San Luis', 'Villa Mercedes', 'Merlo', 'Concarán', 'Justo Daract',
    ],
    'Santa Cruz': [
        'Río Gallegos', 'Caleta Olivia', 'El Calafate', 'Puerto Deseado', 'Pico Truncado', 'Perito Moreno', 'Puerto San Julián',
    ],
    'Santa Fe': [
        'Santa Fe', 'Rosario', 'Rafaela', 'Venado Tuerto', 'Reconquista', 'Casilda',
        'San Lorenzo', 'Villa Constitución', 'Esperanza', 'Santo Tomé', 'Sunchales',
    ],
    'Santiago del Estero': [
        'Santiago del Estero', 'La Banda', 'Termas de Río Hondo', 'Añatuya', 'Frías', 'Fernández',
    ],
    'Tierra del Fuego, Antártida e Islas del Atlántico Sur': [
        'Ushuaia', 'Río Grande', 'Tolhuin',
    ],
    'Tucumán': [
        'San Miguel de Tucumán', 'Yerba Buena', 'Tafí Viejo', 'Concepción', 'Aguilares', 'Monteros', 'Famaillá', 'Tafí del Valle',
    ],
}

# La ciudad "Bahia Blanca" (sin tilde) puede haber quedado cargada a mano de
# antes, sin provincia — la fusionamos con "Bahía Blanca" (con tilde) en vez
# de dejar un duplicado.
ALIAS_CIUDADES = {
    'Bahia Blanca': 'Bahía Blanca',
}


def poblar(apps, schema_editor):
    Pais = apps.get_model('core', 'Pais')
    Provincia = apps.get_model('core', 'Provincia')
    Ciudad = apps.get_model('core', 'Ciudad')

    argentina, _ = Pais.objects.get_or_create(nombre='Argentina', defaults={'activo': True})

    for nombre_provincia, ciudades in PROVINCIAS_Y_CIUDADES.items():
        provincia, _ = Provincia.objects.get_or_create(
            nombre=nombre_provincia, pais=argentina, defaults={'activa': True}
        )
        for nombre_ciudad in ciudades:
            Ciudad.objects.get_or_create(
                nombre=nombre_ciudad, provincia=provincia,
                defaults={'pais': argentina, 'activa': True},
            )

    for nombre_viejo, nombre_nuevo in ALIAS_CIUDADES.items():
        vieja = Ciudad.objects.filter(nombre=nombre_viejo, provincia__isnull=True).first()
        nueva = Ciudad.objects.filter(nombre=nombre_nuevo).exclude(pk=vieja.pk if vieja else None).first()
        if vieja and nueva:
            # Pasamos cualquier nutricionista que ya tuviera la ciudad vieja a la nueva
            Nutricionista = apps.get_model('core', 'Nutricionista')
            Nutricionista.objects.filter(ciudad=vieja).update(ciudad=nueva)
            vieja.delete()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0032_provincia_ciudad_provincia'),
    ]

    operations = [
        migrations.RunPython(poblar, noop),
    ]
