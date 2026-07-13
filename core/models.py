import math
import uuid
import logging
from datetime import date, datetime, timedelta
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator, MaxValueValidator
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.text import slugify

from .storage_backends import storage_archivos_clinicos

logger = logging.getLogger(__name__)


def validar_tamano_archivo(archivo):
    limite_mb = 5
    if archivo.size > limite_mb * 1024 * 1024:
        raise ValidationError(f'El archivo no puede superar los {limite_mb} MB.')


class Pais(models.Model):
    nombre = models.CharField(max_length=100, verbose_name='País')
    codigo = models.CharField(max_length=3, blank=True, verbose_name='Código ISO')
    activo = models.BooleanField(
        default=True, verbose_name='Activo',
        help_text='Solo los países activos aparecen para elegir en el registro y en "Quiero ser parte".',
    )
    # Datos para pago por transferencia bancaria — alternativa manual a los
    # links de Mercado Pago. Como no hay forma automática de confirmar que
    # llegó, el mail le pide al interesado el comprobante.
    transferencia_alias = models.CharField(max_length=100, blank=True, verbose_name='Alias de transferencia')
    transferencia_cvu = models.CharField(max_length=30, blank=True, verbose_name='CVU / CBU')
    transferencia_titular = models.CharField(max_length=150, blank=True, verbose_name='Titular de la cuenta')

    class Meta:
        verbose_name = 'País'
        verbose_name_plural = 'Países'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Ciudad(models.Model):
    nombre = models.CharField(max_length=100, verbose_name='Ciudad')
    pais = models.ForeignKey(
        Pais, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='País'
    )
    activa = models.BooleanField(default=True, verbose_name='Activa')

    class Meta:
        verbose_name = 'Ciudad'
        verbose_name_plural = 'Ciudades'
        ordering = ['nombre']

    def __str__(self):
        if self.pais:
            return f'{self.nombre}, {self.pais.nombre}'
        return self.nombre


class ObraSocial(models.Model):
    nombre = models.CharField(max_length=100)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Obra Social'
        verbose_name_plural = 'Obras Sociales'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class ContactoInteresado(models.Model):
    PLANES = [
        ('publicidad', 'Solo publicidad (perfil en web e Instagram)'),
        ('herramientas', 'Publicidad + Herramientas (turnero, pacientes, etc.)'),
        ('sin_definir', 'Todavia no lo decidi'),
    ]
    nombre = models.CharField(max_length=100, blank=True, verbose_name='Nombre')
    apellido = models.CharField(max_length=100, blank=True, verbose_name='Apellido')
    email = models.EmailField(verbose_name='Email')
    telefono = models.CharField(max_length=20, blank=True, verbose_name='Telefono')
    pais = models.ForeignKey(
        Pais, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='País',
        help_text='Determina qué link de Mercado Pago y qué precio recibe en el mail de planes.',
    )
    plan_interes = models.CharField(
        max_length=20, choices=PLANES, default='sin_definir', verbose_name='Plan de interes'
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    contactado = models.BooleanField(default=False, verbose_name='Contactado')

    class Meta:
        verbose_name = 'Contacto interesado'
        verbose_name_plural = 'Contactos interesados'
        ordering = ['-creado_en']

    def __str__(self):
        return f'{self.nombre} {self.apellido} ({self.email})'


class CodigoDescuento(models.Model):
    """Código de descuento para la suscripción, generalmente ligado a un
    nutricionista que trae clientes nuevos (ej. 'LEANDRO10'). Cada vez que se
    usa en un registro, se le avisa por mail al nutricionista referente — el
    pago del acuerdo entre ese nutricionista y la plataforma se maneja aparte,
    Django solo trackea el uso y avisa."""
    codigo = models.CharField(max_length=30, unique=True, verbose_name='Código')
    nutricionista_referente = models.ForeignKey(
        'Nutricionista', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='codigos_descuento', verbose_name='Nutricionista que lo promociona',
        help_text='Si un nutricionista te trae clientes con este código, elegilo acá — se le avisa por mail cada uso.',
    )
    porcentaje_descuento = models.PositiveSmallIntegerField(
        verbose_name='% de descuento',
        validators=[MinValueValidator(1), MaxValueValidator(100)],
    )
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Código de descuento'
        verbose_name_plural = 'Códigos de descuento'
        ordering = ['-creado_en']

    def __str__(self):
        return f'{self.codigo} (-{self.porcentaje_descuento}%)'


class Nutricionista(models.Model):

    ESPECIALIDADES = [
        ('clinica', 'Nutricion clinica'),
        ('deportiva', 'Nutricion deportiva'),
        ('infantil', 'Nutricion infantil'),
        ('embarazo', 'Embarazo y lactancia'),
        ('vegana', 'Vegetarianismo y veganismo'),
        ('diabetes', 'Diabetes'),
        ('tca', 'Trastornos de la conducta alimentaria'),
        ('obesidad', 'Obesidad'),
        ('otra', 'Otra'),
    ]

    EDADES = [
        ('ninos', 'Ninos'),
        ('adolescentes', 'Adolescentes'),
        ('adultos', 'Adultos'),
        ('mayores', 'Adultos mayores'),
    ]

    MODALIDADES = [
        ('presencial', 'Presencial'),
        ('virtual', 'Virtual'),
        ('ambas', 'Presencial y virtual'),
    ]

    TIPOS = [
        ('base', 'Solo publicidad'),
        ('premium', 'Publicidad + Herramientas'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='nutricionista')
    bio = models.TextField(blank=True, verbose_name='Biografia')
    especialidades = models.CharField(
        max_length=200, blank=True,
        help_text='Separadas por coma. Ejemplo: clinica,deportiva'
    )
    matricula = models.CharField(max_length=50, verbose_name='Matricula')
    telefono = models.CharField(max_length=20, blank=True)
    MENSAJE_RECORDATORIO_DEFAULT = (
        'Hola {nombre}, te recordamos tu turno de hoy a las {hora} hs con {nutricionista}. ¡Te esperamos!'
    )
    mensaje_recordatorio = models.TextField(
        blank=True, verbose_name='Mensaje de recordatorio (WhatsApp)',
        help_text='Se manda a cada paciente el día de su turno. Podés usar {nombre}, {hora} y '
                   '{nutricionista} — se reemplazan solos. Si lo dejás vacío, se usa el mensaje por default.',
    )
    slug = models.SlugField(unique=True, blank=True)
    aprobado = models.BooleanField(default=False, verbose_name='Aprobado / Activo')
    creado_en = models.DateTimeField(auto_now_add=True)
    fecha_aprobacion = models.DateField(
        null=True, blank=True, verbose_name='Fecha de aprobación',
        help_text='Se completa sola la primera vez que se tilda "Aprobado". No se pisa después.',
    )
    proxima_revision_pago = models.DateField(
        null=True, blank=True, verbose_name='Vencimiento de la suscripción',
        help_text='Se actualiza sola cada vez que se confirma un pago (registro o renovación). '
                   'A los 5 días de vencida sin pagar, la cuenta se suspende automáticamente.',
    )
    tipo = models.CharField(
        max_length=10, choices=TIPOS, default='premium', verbose_name='Plan',
        help_text='Base = solo perfil publico. Premium = perfil + dashboard.'
    )
    destacado = models.BooleanField(default=False, verbose_name='Destacado en home')
    foto = models.FileField(
        upload_to='nutricionistas/', blank=True, null=True,
        validators=[validar_tamano_archivo, FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp'])],
    )
    ciudad = models.ForeignKey(
        Ciudad, on_delete=models.SET_NULL, null=True, blank=True
    )
    pais = models.ForeignKey(
        Pais, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='País',
        help_text='Se elige en el registro. Determina el plan/precio de suscripción que se le ofrece.',
    )
    codigo_descuento_usado = models.ForeignKey(
        CodigoDescuento, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='usos', verbose_name='Código de descuento usado',
    )
    exento_de_pago = models.BooleanField(
        default=False, verbose_name='Exento de pago (cortesía)',
        help_text='Si está tildado, esta cuenta nunca se suspende por falta de pago y no necesita renovar.',
    )
    oculto = models.BooleanField(
        default=False, verbose_name='Oculto (cuenta interna/de prueba)',
        help_text='No aparece en el directorio público ni suma en las estadísticas del panel. '
                   'El dashboard le sigue funcionando normal — es solo para cuentas tuyas de prueba.',
    )
    obras_sociales = models.ManyToManyField(
        ObraSocial, blank=True, verbose_name='Obras sociales'
    )
    edades_atendidas = models.CharField(
        max_length=200, blank=True, verbose_name='Edades que atiende',
        help_text='Separadas por coma. Opciones: ninos, adolescentes, adultos, mayores'
    )
    modalidad = models.CharField(
        max_length=20, choices=MODALIDADES, default='ambas', verbose_name='Modalidad'
    )
    acepta_obras_sociales = models.BooleanField(default=False, verbose_name='Acepta obras sociales')
    obras_sociales_detalle = models.TextField(
        blank=True, verbose_name='Detalle de obras sociales'
    )

    class Meta:
        verbose_name = 'Nutricionista'
        verbose_name_plural = 'Nutricionistas'

    def __str__(self):
        return f'{self.user.get_full_name()} ({self.matricula})'

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.user.get_full_name() or self.user.username)
            slug = base_slug
            n = 1
            while Nutricionista.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base_slug}-{n}'
                n += 1
            self.slug = slug
        if self.aprobado and not self.fecha_aprobacion:
            self.fecha_aprobacion = date.today()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('perfil_publico', kwargs={'slug': self.slug})

    def dias_para_vencimiento(self):
        """Días que faltan hasta el vencimiento de la suscripción. Negativo si
        ya venció. None si todavía no se calculó (cuenta recién creada, antes
        del primer pago)."""
        if not self.proxima_revision_pago:
            return None
        return (self.proxima_revision_pago - date.today()).days

    def suspendido_por_pago(self):
        """True si pasaron más de 5 días del vencimiento sin que se haya
        renovado — momento en el que se bloquea el acceso a la cuenta. Las
        cuentas exentas de pago nunca se suspenden."""
        if self.exento_de_pago:
            return False
        dias = self.dias_para_vencimiento()
        return dias is not None and dias < -5

    def extender_vencimiento(self, meses):
        """Extiende la fecha de vencimiento la cantidad de meses pagados,
        contando desde el vencimiento actual (o desde hoy si ya estaba
        vencida) — así nunca se pierden días ya pagados ni se le regalan
        días extra a quien pagó atrasado."""
        from .utils import sumar_un_mes
        base = self.proxima_revision_pago or date.today()
        if base < date.today():
            base = date.today()
        for _ in range(meses):
            base = sumar_un_mes(base)
        self.proxima_revision_pago = base
        self.save(update_fields=['proxima_revision_pago'])

    def get_edades_list(self):
        if not self.edades_atendidas:
            return []
        return [e.strip() for e in self.edades_atendidas.split(',') if e.strip()]

    def get_edades_display(self):
        labels = dict([
            ('ninos', 'Ninos'), ('adolescentes', 'Adolescentes'),
            ('adultos', 'Adultos'), ('mayores', 'Adultos mayores')
        ])
        return [labels.get(e, e) for e in self.get_edades_list()]

    def get_especialidades_list(self):
        if not self.especialidades:
            return []
        return [e.strip() for e in self.especialidades.split(',') if e.strip()]

    def get_especialidades_display(self):
        labels = dict(self.ESPECIALIDADES)
        return [labels.get(e, e) for e in self.get_especialidades_list()]


class Egreso(models.Model):
    """Gasto operativo tuyo (del dueño de la plataforma) — solo para tu propio
    control de ganancia neta estimada en el panel. No tiene relación con los
    nutricionistas ni con Mercado Pago, es carga manual."""
    fecha = models.DateField(default=date.today, verbose_name='Fecha')
    concepto = models.CharField(max_length=200, verbose_name='Concepto')
    monto = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Monto')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Egreso'
        verbose_name_plural = 'Egresos'
        ordering = ['-fecha', '-creado_en']

    def __str__(self):
        return f'{self.fecha} — {self.concepto} — ${self.monto}'


class PagoSuscripcion(models.Model):
    """Un cobro de la suscripción a la plataforma — tanto el pago inicial del
    registro como cada renovación posterior. Siempre es un pago único
    (Checkout Pro) por la cantidad de meses que el profesional eligió pagar
    de una vez; no hay cobro recurrente automático de Mercado Pago. Al
    confirmarse, extiende la fecha de vencimiento esa cantidad de meses."""
    nutricionista = models.ForeignKey(
        Nutricionista, on_delete=models.CASCADE, related_name='pagos_suscripcion'
    )
    meses = models.PositiveSmallIntegerField(verbose_name='Meses pagados')
    monto = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Monto')
    mp_preference_id = models.CharField(max_length=100, blank=True, editable=False)
    confirmado = models.BooleanField(default=False, editable=False)
    creado_en = models.DateTimeField(auto_now_add=True)
    confirmado_en = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        verbose_name = 'Pago de suscripción'
        verbose_name_plural = 'Pagos de suscripción'
        ordering = ['-creado_en']

    def __str__(self):
        return f'{self.nutricionista} — {self.meses} mes(es) — ${self.monto}'


class Paciente(models.Model):

    SEXOS = [
        ('M', 'Masculino'),
        ('F', 'Femenino'),
        ('otro', 'Otro / Prefiero no decir'),
    ]

    OBJETIVOS = [
        ('bajar_peso', 'Bajar de peso'),
        ('subir_peso', 'Subir de peso'),
        ('ganar_musculo', 'Ganar masa muscular'),
        ('mantener', 'Mantener peso actual'),
        ('rendimiento', 'Mejorar rendimiento deportivo'),
        ('salud', 'Mejorar salud general'),
        ('otro', 'Otro'),
    ]

    ALCOHOL = [
        ('no', 'No consume'),
        ('ocasional', 'Ocasional'),
        ('frecuente', 'Frecuente'),
    ]

    nutricionista = models.ForeignKey(
        Nutricionista, on_delete=models.CASCADE, related_name='pacientes'
    )
    nombre = models.CharField(max_length=100, verbose_name='Nombre')
    apellido = models.CharField(max_length=100, verbose_name='Apellido')
    email = models.EmailField(blank=True, verbose_name='Email')
    telefono = models.CharField(max_length=20, blank=True, verbose_name='Telefono')
    fecha_nacimiento = models.DateField(null=True, blank=True, verbose_name='Fecha de nacimiento')
    sexo = models.CharField(max_length=10, choices=SEXOS, blank=True, verbose_name='Sexo')
    dni = models.CharField(max_length=20, blank=True, verbose_name='DNI')
    direccion = models.CharField(max_length=200, blank=True, verbose_name='Direccion')
    obra_social = models.ForeignKey(
        ObraSocial, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Obra social'
    )
    activo = models.BooleanField(default=True, verbose_name='Activo')
    notas_internas = models.TextField(blank=True, verbose_name='Notas internas')
    creado_en = models.DateTimeField(auto_now_add=True)
    objetivo = models.CharField(
        max_length=20, choices=OBJETIVOS, blank=True, verbose_name='Objetivo principal'
    )
    objetivo_detalle = models.TextField(blank=True, verbose_name='Detalle del objetivo')
    derivado_por_medico = models.BooleanField(default=False, verbose_name='Derivado por medico')
    nombre_medico = models.CharField(max_length=100, blank=True, verbose_name='Nombre del medico')
    enfermedades = models.TextField(blank=True, verbose_name='Enfermedades preexistentes')
    alergias = models.TextField(blank=True, verbose_name='Alergias e intolerancias alimentarias')
    medicacion_actual = models.TextField(blank=True, verbose_name='Medicacion actual')
    cirugias_previas = models.TextField(blank=True, verbose_name='Cirugias previas')
    antecedentes_familiares = models.TextField(blank=True, verbose_name='Antecedentes familiares relevantes')
    actividad_fisica_tipo = models.CharField(max_length=100, blank=True, verbose_name='Tipo de actividad fisica')
    actividad_fisica_frecuencia = models.CharField(max_length=100, blank=True, verbose_name='Frecuencia / duracion')
    horas_sueno = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, verbose_name='Horas de sueno')
    consume_alcohol = models.CharField(max_length=20, choices=ALCOHOL, blank=True, verbose_name='Consumo de alcohol')
    consume_tabaco = models.BooleanField(default=False, verbose_name='Consume tabaco')
    nivel_estres = models.CharField(max_length=100, blank=True, verbose_name='Nivel de estres percibido')
    agua_diaria_litros = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, verbose_name='Agua diaria (litros)')
    comidas_por_dia = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Comidas por dia')

    # Portal del paciente: entra con su DNI como usuario y contraseña inicial.
    # No usa el modelo User de Django (evita choques de username si el mismo
    # DNI aparece en la cartera de dos nutricionistas distintos) — es un login
    # propio, con su propio hash de contraseña.
    portal_password = models.CharField(max_length=128, blank=True, editable=False)
    portal_debe_cambiar_password = models.BooleanField(
        default=True, editable=False,
        verbose_name='Debe cambiar contraseña del portal',
    )

    class Meta:
        verbose_name = 'Paciente'
        verbose_name_plural = 'Pacientes'
        ordering = ['apellido', 'nombre']

    def __str__(self):
        return f'{self.apellido}, {self.nombre}'

    def save(self, *args, **kwargs):
        if self.dni and not self.portal_password:
            from django.contrib.auth.hashers import make_password
            self.portal_password = make_password(self.dni)
        super().save(*args, **kwargs)

    @property
    def nombre_completo(self):
        return f'{self.nombre} {self.apellido}'

    @property
    def edad(self):
        if not self.fecha_nacimiento:
            return None
        hoy = date.today()
        return hoy.year - self.fecha_nacimiento.year - (
            (hoy.month, hoy.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day)
        )


class Medicion(models.Model):
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name='mediciones')
    fecha = models.DateField(default=date.today, verbose_name='Fecha')

    # Basicos
    peso_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='Peso (kg)')
    altura_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name='Altura (cm)')
    pct_grasa = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='% Grasa corporal')
    pct_musculo = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='% Masa muscular')
    cintura_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name='Cintura (cm)')
    cadera_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name='Cadera (cm)')

    # Diametros oseos ISAK (cm)
    diametro_biacromial = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='Diametro biacromial (cm)')
    diametro_torax_transverso = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='Diametro torax transverso (cm)')
    diametro_torax_ap = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='Diametro torax anteroposterior (cm)')
    diametro_bi_iliocrestideo = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='Diametro bi-iliocrestideo (cm)')
    diametro_humeral = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='Diametro humeral (cm)')
    diametro_femoral = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='Diametro femoral (cm)')

    # Perimetros completos ISAK (cm)
    perimetro_brazo_relajado = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name='Perimetro brazo relajado (cm)')
    perimetro_brazo_flexionado = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name='Perimetro brazo flexionado (cm)')
    perimetro_antebrazo = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name='Perimetro antebrazo (cm)')
    perimetro_torax = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name='Perimetro torax mesoesternal (cm)')
    perimetro_muslo_superior = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name='Perimetro muslo superior (cm)')
    perimetro_muslo_medial = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name='Perimetro muslo medial (cm)')
    perimetro_pantorrilla = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name='Perimetro pantorrilla maxima (cm)')

    # Pliegues cutaneos ISAK (mm)
    pliegue_tricipital = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='Pliegue tricipital (mm)')
    pliegue_subescapular = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='Pliegue subescapular (mm)')
    pliegue_supraespinal = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='Pliegue supraespinal (mm)')
    pliegue_abdominal = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='Pliegue abdominal (mm)')
    pliegue_muslo = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='Pliegue muslo medial (mm)')
    pliegue_pantorrilla = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='Pliegue pantorrilla (mm)')
    pliegues = models.TextField(blank=True, verbose_name='Notas pliegues')

    # Fraccionamiento 5 masas (D. Kerr 1988)
    masa_adiposa_kg = models.DecimalField(max_digits=5, decimal_places=3, null=True, blank=True, verbose_name='Masa adiposa (kg)')
    masa_adiposa_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='Masa adiposa (%)')
    masa_muscular_kg = models.DecimalField(max_digits=5, decimal_places=3, null=True, blank=True, verbose_name='Masa muscular (kg)')
    masa_muscular_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='Masa muscular (%)')
    masa_residual_kg = models.DecimalField(max_digits=5, decimal_places=3, null=True, blank=True, verbose_name='Masa residual (kg)')
    masa_residual_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='Masa residual (%)')
    masa_osea_kg = models.DecimalField(max_digits=5, decimal_places=3, null=True, blank=True, verbose_name='Masa osea (kg)')
    masa_osea_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='Masa osea (%)')
    masa_piel_kg = models.DecimalField(max_digits=5, decimal_places=3, null=True, blank=True, verbose_name='Masa piel (kg)')
    masa_piel_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='Masa piel (%)')

    # Somatotipo (Heath & Carter 1990)
    soma_endo = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, verbose_name='Endomorfia')
    soma_meso = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, verbose_name='Mesomorfia')
    soma_ecto = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, verbose_name='Ectomorfia')

    # Metabolismo y peso ideal
    metabolismo_basal_kcal = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name='Metabolismo basal (kcal)')
    peso_ideal_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='Peso ideal (kg)')

    observaciones = models.TextField(blank=True, verbose_name='Observaciones')

    class Meta:
        verbose_name = 'Medicion'
        verbose_name_plural = 'Mediciones'
        ordering = ['-fecha']

    def __str__(self):
        return f'Medicion {self.paciente} - {self.fecha}'

    # ──────────────────────────────────────────────────────────────────────────
    # Cálculo automático de composición corporal (se llama desde save())
    # ──────────────────────────────────────────────────────────────────────────
    def calcular_composicion(self):
        """
        Fraccionamiento 5 masas (D. Kerr 1988):
          - Adiposa  : Durnin & Womersley (1974) + Siri (1956)
          - Osea     : Rocha (1975)  MO = 3.02*(H*Dhu*Dfe*400)^0.712
          - Residual : Wurc (1974)   M=11.6% / F=10.9% del peso
          - Piel     : BSA (DuBois) * 1.90 kg/m2
          - Muscular : por sustraccion
        pct_grasa sigue siendo Faulkner (1968) como referencia clinica.
        """
        def _f(v):
            return float(v) if v is not None else None

        try:
            peso      = _f(self.peso_kg)
            altura_cm = _f(self.altura_cm)
            pt        = _f(self.pliegue_tricipital)
            ps        = _f(self.pliegue_subescapular)
            psp       = _f(self.pliegue_supraespinal)
            pa        = _f(self.pliegue_abdominal)
            pmu_pl    = _f(self.pliegue_muslo)
            ppa_pl    = _f(self.pliegue_pantorrilla)
            dhu       = _f(self.diametro_humeral)
            dfe       = _f(self.diametro_femoral)
            pbf       = _f(self.perimetro_brazo_flexionado)
            pbr       = _f(self.perimetro_brazo_relajado)
            pmu_per   = _f(self.perimetro_muslo_medial)
            ppa_per   = _f(self.perimetro_pantorrilla)

            try:
                sexo = self.paciente.sexo
                edad = self.paciente.edad
            except Exception:
                sexo = 'M'
                edad = None

            # ── 1. Faulkner (1968): % Grasa — referencia clinica ─────────
            if all(v is not None for v in [pt, ps, psp, pa]):
                pct_g = 5.783 + 0.153 * (pt + ps + psp + pa)
                pct_g = max(3.0, min(pct_g, 70.0))
                self.pct_grasa = round(pct_g, 2)

            # ── 2. Masa Adiposa — Durnin & Womersley (1974) + Siri (1956) ─
            if all(v is not None for v in [pt, ps, psp, pa]):
                sigma4 = pt + ps + psp + pa
                log_s4 = math.log10(sigma4) if sigma4 > 0 else 0
                edad_num = edad if edad else 30
                if sexo == 'F':
                    if edad_num < 17:   a, b = 1.1369, 0.0598
                    elif edad_num < 30: a, b = 1.1549, 0.0678
                    elif edad_num < 40: a, b = 1.1423, 0.0632
                    elif edad_num < 50: a, b = 1.1333, 0.0612
                    else:               a, b = 1.1339, 0.0645
                else:
                    if edad_num < 17:   a, b = 1.1533, 0.0643
                    elif edad_num < 30: a, b = 1.1631, 0.0632
                    elif edad_num < 40: a, b = 1.1765, 0.0744
                    elif edad_num < 50: a, b = 1.1915, 0.0832
                    else:               a, b = 1.1990, 0.0867
                densidad = a - b * log_s4
                if densidad > 0:
                    pct_at = max(3.0, min(495.0 / densidad - 450.0, 70.0))
                    self.masa_adiposa_pct = round(pct_at, 2)
                    if peso:
                        self.masa_adiposa_kg = round(peso * pct_at / 100, 3)

            # ── 3. Masa Osea — Rocha (1975) ──────────────────────────────
            # MO = 3.02 * (H_m * Dhu_m * Dfe_m * 400)^0.712  [H primer grado]
            if all(v is not None for v in [altura_cm, dhu, dfe]) and altura_cm > 0:
                H_m    = altura_cm / 100
                D_hu_m = dhu / 100
                D_fe_m = dfe / 100
                mo_kg  = 3.02 * (H_m * D_hu_m * D_fe_m * 400) ** 0.712
                self.masa_osea_kg  = round(mo_kg, 3)
                if peso:
                    self.masa_osea_pct = round(mo_kg / peso * 100, 2)

            # ── 4. Masa Residual — Wurc (1974) ───────────────────────────
            # M = 11.6% / F = 10.9% del peso corporal
            if peso:
                factor_res = 0.109 if sexo == 'F' else 0.116
                mr_kg = peso * factor_res
                self.masa_residual_kg  = round(mr_kg, 3)
                self.masa_residual_pct = round(factor_res * 100, 2)

            # ── 5. Masa Piel — Kerr (1988) via BSA ───────────────────────
            # BSA = 0.007184 * H_cm^0.725 * peso^0.425  [DuBois & DuBois]
            # Piel = 1.90 kg/m2
            if peso and altura_cm:
                bsa   = 0.007184 * (altura_cm ** 0.725) * (peso ** 0.425)
                mp_kg = 1.90 * bsa
                self.masa_piel_kg  = round(mp_kg, 3)
                self.masa_piel_pct = round(mp_kg / peso * 100, 2)

            # ── 6. Masa Muscular — por sustraccion ────────────────────────
            if (peso
                    and self.masa_adiposa_kg  is not None
                    and self.masa_osea_kg     is not None
                    and self.masa_residual_kg is not None
                    and self.masa_piel_kg     is not None):
                mm_kg = (peso
                         - float(self.masa_adiposa_kg)
                         - float(self.masa_osea_kg)
                         - float(self.masa_residual_kg)
                         - float(self.masa_piel_kg))
                mm_kg = max(0.0, mm_kg)
                self.masa_muscular_kg  = round(mm_kg, 3)
                self.masa_muscular_pct = round(mm_kg / peso * 100, 2)
                self.pct_musculo       = round(mm_kg / peso * 100, 2)

            # ── 7. Metabolismo Basal — Mifflin-St Jeor ───────────────────
            if peso and altura_cm and edad:
                if sexo == 'F':
                    mb = 10 * peso + 6.25 * altura_cm - 5 * edad - 161
                else:
                    mb = 10 * peso + 6.25 * altura_cm - 5 * edad + 5
                self.metabolismo_basal_kcal = round(max(800, mb), 2)

            # ── 8. Somatotipo — Heath & Carter (1990) ────────────────────
            # Endomorfia: X = suma 3 pliegues corregida (en mm, NO log10)
            if all(v is not None for v in [pt, ps, psp]) and altura_cm and altura_cm > 0:
                S3_corr = (pt + ps + psp) * (170.18 / altura_cm)
                if S3_corr > 0:
                    endo = (-0.7182
                            + 0.1451    * S3_corr
                            - 0.00068   * S3_corr ** 2
                            + 0.0000014 * S3_corr ** 3)
                    self.soma_endo = round(max(0.1, endo), 1)

            # Mesomorfia: usa brazo flexionado (CAG) si disponible
            brazo_meso = pbf if pbf is not None else pbr
            if all(v is not None for v in [dhu, dfe, brazo_meso, ppa_per, pt, ppa_pl]) and altura_cm:
                pBC = brazo_meso - math.pi * (pt  / 10)
                pPC = ppa_per    - math.pi * (ppa_pl / 10)
                meso = (0.858 * dhu + 0.601 * dfe
                        + 0.188 * pBC + 0.161 * pPC
                        - 0.131 * altura_cm + 4.5)
                self.soma_meso = round(max(0.1, meso), 1)

            # Ectomorfia
            if peso and altura_cm:
                HWR = altura_cm / (peso ** (1 / 3))
                if HWR >= 40.75:
                    ecto = 0.732 * HWR - 28.58
                elif HWR > 38.25:
                    ecto = 0.463 * HWR - 17.63
                else:
                    ecto = 0.5
                self.soma_ecto = round(max(0.1, ecto), 1)

        except Exception as exc:
            logger.warning('calcular_composicion error en Medicion pk=%s: %s', self.pk, exc)


    def save(self, *args, **kwargs):
        self.calcular_composicion()
        super().save(*args, **kwargs)

    @property
    def imc(self):
        if self.peso_kg and self.altura_cm and self.altura_cm > 0:
            h = float(self.altura_cm) / 100
            return round(float(self.peso_kg) / (h * h), 2)
        return None

    @property
    def imc_categoria(self):
        imc = self.imc
        if imc is None:
            return ''
        if imc < 18.5:
            return 'Bajo peso'
        if imc < 25:
            return 'Normal'
        if imc < 30:
            return 'Sobrepeso'
        if imc < 35:
            return 'Obesidad I'
        if imc < 40:
            return 'Obesidad II'
        return 'Obesidad III'

    @property
    def relacion_cintura_cadera(self):
        if self.cintura_cm and self.cadera_cm and float(self.cadera_cm) > 0:
            return round(float(self.cintura_cm) / float(self.cadera_cm), 3)
        return None

    @property
    def suma_6_pliegues(self):
        vals = [
            self.pliegue_tricipital, self.pliegue_subescapular,
            self.pliegue_supraespinal, self.pliegue_abdominal,
            self.pliegue_muslo, self.pliegue_pantorrilla,
        ]
        nums = [float(v) for v in vals if v is not None]
        if len(nums) == 6:
            return round(sum(nums), 2)
        return None

    @property
    def somatotipo_display(self):
        if self.soma_endo and self.soma_meso and self.soma_ecto:
            return f'{self.soma_endo} - {self.soma_meso} - {self.soma_ecto}'
        return None


class Laboratorio(models.Model):
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name='laboratorios')
    fecha = models.DateField(default=date.today, verbose_name='Fecha del analisis')
    glucemia = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name='Glucemia (mg/dL)')
    colesterol_total = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name='Colesterol total (mg/dL)')
    colesterol_hdl = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name='Colesterol HDL (mg/dL)')
    colesterol_ldl = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name='Colesterol LDL (mg/dL)')
    trigliceridos = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name='Trigliceridos (mg/dL)')
    hemoglobina = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='Hemoglobina (g/dL)')
    ferritina = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name='Ferritina (ng/mL)')
    vitamina_d = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name='Vitamina D (ng/mL)')
    tsh = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True, verbose_name='TSH (mUI/L)')
    archivo_pdf = models.FileField(
        upload_to='laboratorios/', blank=True, null=True, verbose_name='Archivo PDF',
        validators=[validar_tamano_archivo, FileExtensionValidator(allowed_extensions=['pdf'])],
        storage=storage_archivos_clinicos,
    )
    observaciones = models.TextField(blank=True, verbose_name='Observaciones')

    class Meta:
        verbose_name = 'Laboratorio'
        verbose_name_plural = 'Laboratorios'
        ordering = ['-fecha']

    def __str__(self):
        return f'Lab {self.paciente} - {self.fecha}'


class PlanAlimentario(models.Model):
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name='planes')
    fecha = models.DateField(default=date.today, verbose_name='Fecha del plan')
    calorias_objetivo = models.PositiveIntegerField(null=True, blank=True, verbose_name='Calorias objetivo (kcal)')
    pct_proteinas = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name='Proteinas (%)')
    pct_carbohidratos = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name='Carbohidratos (%)')
    pct_grasas = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name='Grasas (%)')
    plan_semanal = models.TextField(blank=True, verbose_name='Plan semanal (descripcion)')
    archivo_pdf = models.FileField(
        upload_to='planes/', blank=True, null=True, verbose_name='Plan en PDF',
        validators=[validar_tamano_archivo, FileExtensionValidator(allowed_extensions=['pdf'])],
        storage=storage_archivos_clinicos,
    )
    observaciones = models.TextField(blank=True, verbose_name='Observaciones')

    class Meta:
        verbose_name = 'Plan alimentario'
        verbose_name_plural = 'Planes alimentarios'
        ordering = ['-fecha']

    def __str__(self):
        return f'Plan {self.paciente} - {self.fecha}'


class ArchivoPaciente(models.Model):
    EXTENSIONES_PERMITIDAS = ['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx']

    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name='archivos')
    nombre = models.CharField(max_length=150, verbose_name='Nombre del archivo')
    archivo = models.FileField(
        upload_to='archivos_pacientes/',
        validators=[validar_tamano_archivo, FileExtensionValidator(allowed_extensions=EXTENSIONES_PERMITIDAS)],
        verbose_name='Archivo',
        storage=storage_archivos_clinicos,
    )
    # Token opaco para el link que se comparte con el paciente por WhatsApp
    # (el paciente no tiene cuenta, así que no puede pasar por login).
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    fecha = models.DateField(default=date.today, verbose_name='Fecha')
    observaciones = models.TextField(blank=True, verbose_name='Observaciones')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Archivo'
        verbose_name_plural = 'Archivos'
        ordering = ['-creado_en']

    def __str__(self):
        return f'{self.nombre} - {self.paciente}'


class Consulta(models.Model):
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name='consultas')
    fecha = models.DateField(default=date.today, verbose_name='Fecha de la consulta')
    peso_dia = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='Peso del dia (kg)')
    observaciones = models.TextField(blank=True, verbose_name='Observaciones / Evolucion')
    cambios_al_plan = models.TextField(blank=True, verbose_name='Cambios al plan')
    proximo_turno = models.DateField(null=True, blank=True, verbose_name='Proximo turno')

    class Meta:
        verbose_name = 'Consulta'
        verbose_name_plural = 'Consultas'
        ordering = ['-fecha']

    def __str__(self):
        return f'Consulta {self.paciente} - {self.fecha}'


class Turno(models.Model):
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('pendiente_sena', 'Esperando seña'),
        ('confirmado', 'Confirmado'),
        ('cancelado', 'Cancelado'),
        ('vencido', 'Vencido (seña impaga)'),
        ('realizado', 'Realizado'),
        ('no_asistio', 'No asistió'),
    ]

    ORIGENES = [
        ('manual', 'Cargado por el nutricionista'),
        ('online', 'Reservado online por el paciente'),
    ]

    nutricionista = models.ForeignKey(Nutricionista, on_delete=models.CASCADE, related_name='turnos')
    paciente = models.ForeignKey(
        Paciente, on_delete=models.SET_NULL, null=True, blank=True, related_name='turnos'
    )
    fecha_hora_inicio = models.DateTimeField(verbose_name='Fecha y hora de inicio')
    duracion_minutos = models.PositiveIntegerField(default=60, verbose_name='Duracion (minutos)')
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente', verbose_name='Estado')
    motivo = models.CharField(max_length=200, blank=True, verbose_name='Motivo')
    notas = models.TextField(blank=True)

    # ── Reserva online ────────────────────────────────────────────────────
    origen = models.CharField(max_length=10, choices=ORIGENES, default='manual', verbose_name='Origen')
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True,
                             help_text='Token para que el paciente gestione su turno sin login')
    nombre_contacto = models.CharField(max_length=100, blank=True, verbose_name='Nombre (reserva online)')
    apellido_contacto = models.CharField(max_length=100, blank=True, verbose_name='Apellido (reserva online)')
    email_contacto = models.EmailField(blank=True, verbose_name='Email (reserva online)')
    telefono_contacto = models.CharField(max_length=30, blank=True, verbose_name='Telefono (reserva online)')

    # ── Seña / pago ───────────────────────────────────────────────────────
    sena_monto = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                     verbose_name='Monto de la seña')
    sena_pagada = models.BooleanField(default=False, verbose_name='Seña pagada')
    sena_pagada_en = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de pago de la seña')
    mp_preference_id = models.CharField(max_length=100, blank=True, verbose_name='ID de preferencia MP')
    mp_payment_id = models.CharField(max_length=100, blank=True, verbose_name='ID de pago MP')
    recordatorio_enviado_en = models.DateTimeField(null=True, blank=True,
                                                   verbose_name='Recordatorio de seña enviado')
    creado_en = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        verbose_name = 'Turno'
        verbose_name_plural = 'Turnos'
        ordering = ['fecha_hora_inicio']

    def __str__(self):
        p = self.paciente.nombre_completo if self.paciente else 'Sin paciente'
        return f'{p} - {timezone.localtime(self.fecha_hora_inicio).strftime("%d/%m/%Y %H:%M")}'

    def hay_sobreturno(self):
        fin = self.fecha_hora_inicio + timedelta(minutes=self.duracion_minutos)
        qs = Turno.objects.filter(
            nutricionista=self.nutricionista,
            fecha_hora_inicio__lt=fin,
            estado__in=['pendiente', 'pendiente_sena', 'confirmado'],
        ).exclude(pk=self.pk)
        return qs.filter(
            fecha_hora_inicio__gte=self.fecha_hora_inicio
        ).exists() or qs.filter(
            fecha_hora_inicio__lt=self.fecha_hora_inicio
        ).filter(
            fecha_hora_inicio__gt=self.fecha_hora_inicio - timedelta(minutes=60)
        ).exists()

    # ── Helpers de reserva online ─────────────────────────────────────────
    @property
    def nombre_display(self):
        if self.paciente:
            return self.paciente.nombre_completo
        if self.nombre_contacto:
            return f'{self.nombre_contacto} {self.apellido_contacto}'.strip()
        return 'Sin paciente'

    @property
    def email_destino(self):
        if self.email_contacto:
            return self.email_contacto
        if self.paciente and self.paciente.email:
            return self.paciente.email
        return ''

    @property
    def telefono_destino(self):
        if self.telefono_contacto:
            return self.telefono_contacto
        if self.paciente and self.paciente.telefono:
            return self.paciente.telefono
        return ''

    @property
    def fecha_fin(self):
        return self.fecha_hora_inicio + timedelta(minutes=self.duracion_minutos)

    def fecha_limite_pago(self, horas_limite):
        """Hora limite para pagar la seña antes de que el turno se libere."""
        return self.fecha_hora_inicio - timedelta(hours=horas_limite)


# ═══════════════════════════════════════════════════════════════════════════
# TURNERO ONLINE — disponibilidad, seña y Mercado Pago
# ═══════════════════════════════════════════════════════════════════════════

class ConfiguracionTurnero(models.Model):
    """Configuracion del turnero online de cada nutricionista."""

    nutricionista = models.OneToOneField(
        Nutricionista, on_delete=models.CASCADE, related_name='turnero'
    )
    activo = models.BooleanField(
        default=False, verbose_name='Turnero online activo',
        help_text='Si esta activo, los pacientes pueden reservar desde tu link publico.'
    )
    duracion_turno_minutos = models.PositiveIntegerField(
        default=30, verbose_name='Duracion de cada turno (minutos)'
    )
    anticipacion_maxima_dias = models.PositiveIntegerField(
        default=30, verbose_name='Hasta cuantos dias hacia adelante se puede reservar'
    )
    anticipacion_minima_horas = models.PositiveIntegerField(
        default=3, verbose_name='Anticipacion minima para reservar (horas)'
    )

    # ── Seña ──────────────────────────────────────────────────────────────
    requiere_sena = models.BooleanField(
        default=True, verbose_name='Pedir seña para confirmar el turno'
    )
    precio_consulta = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Precio de la consulta ($)'
    )
    porcentaje_sena = models.PositiveIntegerField(
        default=50, verbose_name='Porcentaje de seña (%)'
    )
    horas_recordatorio = models.PositiveIntegerField(
        default=24, verbose_name='Enviar recordatorio con link de pago (horas antes)'
    )
    horas_limite_pago = models.PositiveIntegerField(
        default=6, verbose_name='Si no paga, liberar el turno (horas antes)'
    )

    # ── Mercado Pago (OAuth) ──────────────────────────────────────────────
    mp_user_id = models.CharField(max_length=50, blank=True, verbose_name='MP User ID')
    mp_access_token = models.CharField(max_length=200, blank=True)
    mp_refresh_token = models.CharField(max_length=200, blank=True)
    mp_public_key = models.CharField(max_length=200, blank=True)
    mp_token_expira_en = models.DateTimeField(null=True, blank=True)
    mp_conectado_en = models.DateTimeField(null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuracion de turnero'
        verbose_name_plural = 'Configuraciones de turnero'

    def __str__(self):
        return f'Turnero de {self.nutricionista}'

    @property
    def mp_conectado(self):
        return bool(self.mp_access_token)

    @property
    def monto_sena(self):
        if self.precio_consulta and self.porcentaje_sena:
            return round(self.precio_consulta * self.porcentaje_sena / 100, 2)
        return None

    @property
    def listo_para_publicar(self):
        """El turnero puede recibir reservas."""
        if not self.franjas.exists():
            return False
        if self.requiere_sena and (not self.mp_conectado or not self.monto_sena):
            return False
        return True

    def generar_slots(self, fecha):
        """
        Devuelve la lista de datetimes (aware) disponibles para una fecha,
        segun franjas horarias, turnos ocupados, bloqueos y anticipacion.
        """
        tz = timezone.get_current_timezone()
        ahora = timezone.now()
        minimo = ahora + timedelta(hours=self.anticipacion_minima_horas)

        # Bloqueos que cubren la fecha
        if self.bloqueos.filter(fecha_desde__lte=fecha, fecha_hasta__gte=fecha).exists():
            return []

        dia_semana = fecha.weekday()  # 0=lunes
        franjas = self.franjas.filter(dia_semana=dia_semana).order_by('hora_inicio')
        if not franjas:
            return []

        # Turnos que ocupan lugar ese dia
        ocupados = list(
            Turno.objects.filter(
                nutricionista=self.nutricionista,
                fecha_hora_inicio__date=fecha,
                estado__in=['pendiente', 'pendiente_sena', 'confirmado'],
            ).values_list('fecha_hora_inicio', 'duracion_minutos')
        )

        slots = []
        dur = timedelta(minutes=self.duracion_turno_minutos)
        for franja in franjas:
            inicio = timezone.make_aware(datetime.combine(fecha, franja.hora_inicio), tz)
            fin_franja = timezone.make_aware(datetime.combine(fecha, franja.hora_fin), tz)
            actual = inicio
            while actual + dur <= fin_franja:
                if actual >= minimo:
                    fin_slot = actual + dur
                    solapado = any(
                        actual < (o_ini + timedelta(minutes=o_dur)) and fin_slot > o_ini
                        for o_ini, o_dur in ocupados
                    )
                    if not solapado:
                        slots.append(actual)
                actual += dur
        return slots


class FranjaHoraria(models.Model):
    """Franja semanal de atencion. Ej: lunes de 09:00 a 13:00."""

    DIAS = [
        (0, 'Lunes'), (1, 'Martes'), (2, 'Miercoles'), (3, 'Jueves'),
        (4, 'Viernes'), (5, 'Sabado'), (6, 'Domingo'),
    ]

    turnero = models.ForeignKey(
        ConfiguracionTurnero, on_delete=models.CASCADE, related_name='franjas'
    )
    dia_semana = models.PositiveSmallIntegerField(choices=DIAS, verbose_name='Dia')
    hora_inicio = models.TimeField(verbose_name='Desde')
    hora_fin = models.TimeField(verbose_name='Hasta')

    class Meta:
        verbose_name = 'Franja horaria'
        verbose_name_plural = 'Franjas horarias'
        ordering = ['dia_semana', 'hora_inicio']

    def __str__(self):
        return f'{self.get_dia_semana_display()} {self.hora_inicio:%H:%M}-{self.hora_fin:%H:%M}'


class BloqueoFecha(models.Model):
    """Dias bloqueados (vacaciones, feriados, congresos)."""

    turnero = models.ForeignKey(
        ConfiguracionTurnero, on_delete=models.CASCADE, related_name='bloqueos'
    )
    fecha_desde = models.DateField(verbose_name='Desde')
    fecha_hasta = models.DateField(verbose_name='Hasta')
    motivo = models.CharField(max_length=100, blank=True, verbose_name='Motivo')

    class Meta:
        verbose_name = 'Fecha bloqueada'
        verbose_name_plural = 'Fechas bloqueadas'
        ordering = ['fecha_desde']

    def __str__(self):
        return f'{self.fecha_desde} → {self.fecha_hasta} ({self.motivo or "sin motivo"})'