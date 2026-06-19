from datetime import timedelta
from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify


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

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='nutricionista')
    bio = models.TextField(blank=True, verbose_name='Biografia')
    especialidad = models.CharField(
        max_length=20, choices=ESPECIALIDADES, blank=True, verbose_name='Especialidad'
    )
    matricula = models.CharField(max_length=50, verbose_name='Matricula')
    telefono = models.CharField(max_length=20, blank=True, verbose_name='Telefono')
    slug = models.SlugField(unique=True, blank=True)
    aprobado = models.BooleanField(default=False, verbose_name='Aprobado')
    creado_en = models.DateTimeField(auto_now_add=True)

    # Filtros nuevos
    edades_atendidas = models.CharField(
        max_length=200, blank=True, verbose_name='Edades que atiende',
        help_text='Separadas por coma. Opciones: ninos, adolescentes, adultos, mayores'
    )
    modalidad = models.CharField(
        max_length=20, choices=MODALIDADES, default='ambas', verbose_name='Modalidad'
    )
    acepta_obras_sociales = models.BooleanField(default=False, verbose_name='Acepta obras sociales')
    obras_sociales_detalle = models.TextField(
        blank=True, verbose_name='Detalle de obras sociales',
        help_text='Listado de obras sociales que acepta'
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


class Paciente(models.Model):
    nutricionista = models.ForeignKey(
        Nutricionista, on_delete=models.CASCADE, related_name='pacientes'
    )
    nombre = models.CharField(max_length=100, verbose_name='Nombre')
    apellido = models.CharField(max_length=100, verbose_name='Apellido')
    email = models.EmailField(blank=True, verbose_name='Email')
    telefono = models.CharField(max_length=20, blank=True, verbose_name='Telefono')
    fecha_nacimiento = models.DateField(null=True, blank=True, verbose_name='Fecha de nacimiento')
    activo = models.BooleanField(default=True, verbose_name='Activo')
    notas_internas = models.TextField(blank=True, verbose_name='Notas internas')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Paciente'
        verbose_name_plural = 'Pacientes'
        ordering = ['apellido', 'nombre']

    def __str__(self):
        return f'{self.apellido}, {self.nombre}'

    @property
    def nombre_completo(self):