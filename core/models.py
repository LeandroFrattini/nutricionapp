import math
import logging
from datetime import date, timedelta
from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify

logger = logging.getLogger(__name__)


class Pais(models.Model):
    nombre = models.CharField(max_length=100, verbose_name='País')
    codigo = models.CharField(max_length=3, blank=True, verbose_name='Código ISO')
    activo = models.BooleanField(default=True, verbose_name='Activo')

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
    nombre = models.CharField(max_length=100, verbose_name='Nombre')
    apellido = models.CharField(max_length=100, verbose_name='Apellido')
    email = models.EmailField(verbose_name='Email')
    telefono = models.CharField(max_length=20, blank=True, verbose_name='Telefono')
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
    slug = models.SlugField(unique=True, blank=True)
    aprobado = models.BooleanField(default=False, verbose_name='Aprobado / Activo')
    creado_en = models.DateTimeField(auto_now_add=True)
    tipo = models.CharField(
        max_length=10, choices=TIPOS, default='premium', verbose_name='Plan',
        help_text='Base = solo perfil publico. Premium = perfil + dashboard.'
    )
    destacado = models.BooleanField(default=False, verbose_name='Destacado en home')
    foto = models.FileField(upload_to='nutricionistas/', blank=True, null=True)
    ciudad = models.ForeignKey(
        Ciudad, on_delete=models.SET_NULL, null=True, blank=True
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
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('perfil_publico', kwargs={'slug': self.slug})

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

    class Meta:
        verbose_name = 'Paciente'
        verbose_name_plural = 'Pacientes'
        ordering = ['apellido', 'nombre']

    def __str__(self):
        return f'{self.apellido}, {self.nombre}'

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
        Auto-calcula composición corporal a partir de los datos ISAK cargados.
        Fórmulas:
          - Faulkner (1968): % grasa  [4 pliegues]
          - Rocha (1975): masa ósea   [diámetros humeral + femoral]
          - Würch (1974): masa residual
          - Derivada: masa muscular = peso - adiposa - ósea - residual - piel
          - Mifflin-St Jeor: metabolismo basal
          - Heath & Carter (1990): somatotipo
        """
        def _f(v):
            """Convierte Decimal / None → float / None."""
            return float(v) if v is not None else None

        try:
            peso      = _f(self.peso_kg)
            altura_cm = _f(self.altura_cm)
            pt        = _f(self.pliegue_tricipital)      # mm
            ps        = _f(self.pliegue_subescapular)    # mm
            psp       = _f(self.pliegue_supraespinal)    # mm
            pa        = _f(self.pliegue_abdominal)       # mm
            pmu_pl    = _f(self.pliegue_muslo)           # mm
            ppa_pl    = _f(self.pliegue_pantorrilla)     # mm
            dhu       = _f(self.diametro_humeral)        # cm
            dfe       = _f(self.diametro_femoral)        # cm
            pbr       = _f(self.perimetro_brazo_relajado)   # cm
            pmu_per   = _f(self.perimetro_muslo_medial)     # cm
            ppa_per   = _f(self.perimetro_pantorrilla)      # cm

            # Sexo y edad desde el paciente
            try:
                sexo = self.paciente.sexo  # 'M', 'F', 'otro'
                edad = self.paciente.edad  # int o None
            except Exception:
                sexo = 'M'
                edad = None

            # ── 1. Faulkner (1968): % Grasa corporal ─────────────────────
            # Requiere los 4 pliegues: tricipital, subescapular, supraespinal, abdominal
            if all(v is not None for v in [pt, ps, psp, pa]):
                pct_g = 5.783 + 0.153 * (pt + ps + psp + pa)
                pct_g = max(3.0, min(pct_g, 70.0))   # límites fisiológicos
                self.pct_grasa      = round(pct_g, 2)
                self.masa_adiposa_pct = round(pct_g, 2)
                if peso:
                    self.masa_adiposa_kg = round(peso * pct_g / 100, 3)

            # ── 2. Masa Ósea — Rocha (1975) ──────────────────────────────
            # Requiere: altura, diámetro humeral biepicondilar, femoral biepicondilar
            if all(v is not None for v in [altura_cm, dhu, dfe]) and altura_cm > 0:
                H_m    = altura_cm / 100
                D_hu_m = dhu / 100   # cm → m
                D_fe_m = dfe / 100   # cm → m
                mo_kg  = 3.02 * ((H_m ** 2) * D_hu_m * D_fe_m * 400) ** 0.712
                self.masa_osea_kg  = round(mo_kg, 3)
                if peso:
                    self.masa_osea_pct = round(mo_kg / peso * 100, 2)

            # ── 3. Masa Residual — Würch (1974) ──────────────────────────
            if peso:
                factor_res = 0.209 if sexo == 'F' else 0.241
                mr_kg = peso * factor_res
                self.masa_residual_kg  = round(mr_kg, 3)
                self.masa_residual_pct = round(factor_res * 100, 2)

            # ── 4. Masa Piel — estimada (Kerr 1988: ~6.3 % del peso) ─────
            if peso:
                mp_kg = peso * 0.063
                self.masa_piel_kg  = round(mp_kg, 3)
                self.masa_piel_pct = round(6.3, 2)

            # ── 5. Masa Muscular — por sustracción ────────────────────────
            if (peso
                    and self.masa_adiposa_kg is not None
                    and self.masa_osea_kg    is not None
                    and self.masa_residual_kg is not None
                    and self.masa_piel_kg    is not None):
                mm_kg = (peso
                         - float(self.masa_adiposa_kg)
                         - float(self.masa_osea_kg)
                         - float(self.masa_residual_kg)
                         - float(self.masa_piel_kg))
                mm_kg = max(0.0, mm_kg)
                self.masa_muscular_kg  = round(mm_kg, 3)
                self.masa_muscular_pct = round(mm_kg / peso * 100, 2)
                self.pct_musculo       = round(mm_kg / peso * 100, 2)

            # ── 6. Metabolismo Basal — Mifflin-St Jeor ───────────────────
            if peso and altura_cm and edad:
                if sexo == 'F':
                    mb = 10 * peso + 6.25 * altura_cm - 5 * edad - 161
                else:
                    mb = 10 * peso + 6.25 * altura_cm - 5 * edad + 5
                self.metabolismo_basal_kcal = round(max(800, mb), 2)

            # ── 7. Somatotipo — Heath & Carter (1990) ────────────────────

            # Endomorfia: usa 3 pliegues corregidos por talla
            if all(v is not None for v in [pt, ps, psp]) and altura_cm and altura_cm > 0:
                S3_corr = (pt + ps + psp) * (170.18 / altura_cm)
                if S3_corr > 0:
                    X = math.log10(S3_corr)
                    endo = -0.7182 + 0.1451 * X - 0.00068 * X ** 2 + 0.0000014 * X ** 3
                    self.soma_endo = round(max(0.1, endo), 1)

            # Mesomorfia: diámetros + perímetros corregidos por pliegue
            if all(v is not None for v in [dhu, dfe, pbr, ppa_per, pt, ppa_pl]) and altura_cm:
                pBC = pbr - math.pi * (pt / 10)       # perímetro brazo corregido (cm)
                pPC = ppa_per - math.pi * (ppa_pl / 10)  # perímetro pantorrilla corregido (cm)
                meso = (0.858 * dhu + 0.601 * dfe
                        + 0.188 * pBC + 0.161 * pPC
                        - 0.131 * altura_cm + 4.5)
                self.soma_meso = round(max(0.1, meso), 1)

            # Ectomorfia: índice altura/raíz cúbica del peso
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
    archivo_pdf = models.FileField(upload_to='laboratorios/', blank=True, null=True, verbose_name='Archivo PDF')
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
    archivo_pdf = models.FileField(upload_to='planes/', blank=True, null=True, verbose_name='Plan en PDF')
    observaciones = models.TextField(blank=True, verbose_name='Observaciones')

    class Meta:
        verbose_name = 'Plan alimentario'
        verbose_name_plural = 'Planes alimentarios'
        ordering = ['-fecha']

    def __str__(self):
        return f'Plan {self.paciente} - {self.fecha}'


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
        ('confirmado', 'Confirmado'),
        ('cancelado', 'Cancelado'),
        ('realizado', 'Realizado'),
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

    class Meta:
        verbose_name = 'Turno'
        verbose_name_plural = 'Turnos'
        ordering = ['fecha_hora_inicio']

    def __str__(self):
        p = self.paciente.nombre_completo if self.paciente else 'Sin paciente'
        return f'{p} - {self.fecha_hora_inicio.strftime("%d/%m/%Y %H:%M")}'

    def hay_sobreturno(self):
        fin = self.fecha_hora_inicio + timedelta(minutes=self.duracion_minutos)
        qs = Turno.objects.filter(
            nutricionista=self.nutricionista,
            fecha_hora_inicio__lt=fin,
            estado__in=['pendiente', 'confirmado'],
        ).exclude(pk=self.pk)
        return qs.filter(
            fecha_hora_inicio__gte=self.fecha_hora_inicio
        ).exists() or qs.filter(
            fecha_hora_inicio__lt=self.fecha_hora_inicio
        ).filter(
            fecha_hora_inicio__gt=self.fecha_hora_inicio - timedelta(minutes=60)
        ).exists()
