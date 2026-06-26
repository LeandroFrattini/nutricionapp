from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Nutricionista, Paciente, Turno, Medicion, Laboratorio, PlanAlimentario, Consulta

CSS = (
    'w-full px-3 py-2 border border-gray-300 rounded-lg '
    'focus:outline-none focus:ring-2 focus:ring-green-500'
)


def _apply_css(form):
    for field in form.fields.values():
        field.widget.attrs.setdefault('class', CSS)


class RegistroForm(UserCreationForm):
    first_name = forms.CharField(max_length=100, label='Nombre', required=True)
    last_name = forms.CharField(max_length=100, label='Apellido', required=True)
    email = forms.EmailField(label='Email', required=True)
    matricula = forms.CharField(max_length=50, label='Matricula profesional', required=True)
    especialidad = forms.CharField(max_length=100, label='Especialidad', required=False)
    telefono = forms.CharField(max_length=20, label='Telefono', required=False)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_css(self)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.is_active = False
        if commit:
            user.save()
            Nutricionista.objects.create(
                user=user,
                matricula=self.cleaned_data['matricula'],
                especialidades=self.cleaned_data.get('especialidad', ''),
                telefono=self.cleaned_data.get('telefono', ''),
            )
        return user


class PerfilForm(forms.ModelForm):
    first_name = forms.CharField(max_length=100, label='Nombre')
    last_name = forms.CharField(max_length=100, label='Apellido')

    # Checkbox pills — se guardan como string separado por comas en el modelo
    especialidades = forms.MultipleChoiceField(
        choices=Nutricionista.ESPECIALIDADES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Especialidades',
    )
    edades_atendidas = forms.MultipleChoiceField(
        choices=Nutricionista.EDADES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Edades que atendés',
    )
    modalidad = forms.ChoiceField(
        choices=Nutricionista.MODALIDADES,
        widget=forms.RadioSelect,
        required=False,
        label='Modalidad de atención',
    )

    class Meta:
        model = Nutricionista
        fields = [
            'foto', 'matricula', 'telefono', 'bio',
            'ciudad', 'obras_sociales', 'acepta_obras_sociales',
        ]
        labels = {
            'foto': 'Foto de perfil',
            'matricula': 'Matrícula',
            'telefono': 'Teléfono',
            'bio': 'Sobre mí (texto que ven los pacientes)',
            'ciudad': 'Ciudad',
            'obras_sociales': 'Obras sociales que aceptás',
            'acepta_obras_sociales': 'Acepto obras sociales',
        }
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
            'obras_sociales': forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        inst = self.instance
        if inst and inst.pk:
            self.initial['first_name'] = inst.user.first_name
            self.initial['last_name'] = inst.user.last_name
            # Convertir strings "clinica,deportiva" → ['clinica', 'deportiva']
            self.initial['especialidades'] = [
                e.strip() for e in (inst.especialidades or '').split(',') if e.strip()
            ]
            self.initial['edades_atendidas'] = [
                e.strip() for e in (inst.edades_atendidas or '').split(',') if e.strip()
            ]
            self.initial['modalidad'] = inst.modalidad
        _apply_css(self)
        # Campos que NO deben tener estilos de input de texto
        for fname in ['especialidades', 'edades_atendidas', 'modalidad',
                      'foto', 'obras_sociales', 'acepta_obras_sociales']:
            if fname in self.fields:
                self.fields[fname].widget.attrs.pop('class', None)
        self.fields['foto'].required = False

    def clean_especialidades(self):
        """Convierte lista → string separado por comas para guardar en CharField."""
        return ','.join(self.cleaned_data.get('especialidades', []))

    def clean_edades_atendidas(self):
        return ','.join(self.cleaned_data.get('edades_atendidas', []))

    def save(self, commit=True):
        nutricionista = super().save(commit=False)
        nutricionista.user.first_name = self.cleaned_data['first_name']
        nutricionista.user.last_name = self.cleaned_data['last_name']
        # Asignar campos declarados que no son parte de Meta.fields
        nutricionista.especialidades = self.cleaned_data.get('especialidades', '')
        nutricionista.edades_atendidas = self.cleaned_data.get('edades_atendidas', '')
        nutricionista.modalidad = self.cleaned_data.get('modalidad', '')
        if commit:
            nutricionista.user.save()
            nutricionista.save()
            self._save_m2m()
        return nutricionista


class ContactoForm(forms.Form):
    nombre = forms.CharField(max_length=100, label='Nombre')
    apellido = forms.CharField(max_length=100, label='Apellido')
    email = forms.EmailField(label='Email')
    telefono = forms.CharField(max_length=20, label='WhatsApp / Teléfono', required=False)
    pacientes_semana = forms.ChoiceField(
        choices=[
            ('', '— Seleccioná —'),
            ('menos_10', 'Menos de 10 pacientes'),
            ('10_30', 'Entre 10 y 30 pacientes'),
            ('mas_30', 'Más de 30 pacientes'),
        ],
        label='¿Cuántos pacientes atendés por semana?',
        required=False,
    )
    plan_interes = forms.ChoiceField(
        choices=[
            ('herramientas', 'Plan Completo — Publicidad + Herramientas'),
            ('publicidad', 'Plan Básico — Solo publicidad'),
            ('sin_definir', 'Todavía no lo decidí'),
        ],
        label='¿Qué plan te interesa?',
        initial='herramientas',
    )

    def __init__(self, *args, **kwargs):
        plan = kwargs.pop('plan_inicial', None)
        super().__init__(*args, **kwargs)
        if plan and not args:  # solo en formulario vacío
            self.fields['plan_interes'].initial = plan
        _apply_css(self)
        self.fields['plan_interes'].widget.attrs.pop('class', None)


class PacienteForm(forms.ModelForm):
    class Meta:
        model = Paciente
        exclude = ['nutricionista', 'creado_en', 'activo']
        widgets = {
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date'}),
            'notas_internas': forms.Textarea(attrs={'rows': 3}),
            'objetivo_detalle': forms.Textarea(attrs={'rows': 2}),
            'enfermedades': forms.Textarea(attrs={'rows': 3}),
            'alergias': forms.Textarea(attrs={'rows': 2}),
            'medicacion_actual': forms.Textarea(attrs={'rows': 2}),
            'cirugias_previas': forms.Textarea(attrs={'rows': 2}),
            'antecedentes_familiares': forms.Textarea(attrs={'rows': 2}),
            'nivel_estres': forms.TextInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_css(self)


class MedicionForm(forms.ModelForm):
    """
    Solo muestra los campos que el profesional ingresa manualmente.
    Los campos calculados (composición corporal, somatotipo, metabolismo)
    se calculan automáticamente en Medicion.save() y se muestran como
    resultados de solo lectura en el template.
    """
    class Meta:
        model = Medicion
        fields = [
            # Básicos
            'fecha', 'peso_kg', 'altura_cm', 'cintura_cm', 'cadera_cm',
            # Diámetros
            'diametro_biacromial', 'diametro_torax_transverso', 'diametro_torax_ap',
            'diametro_bi_iliocrestideo', 'diametro_humeral', 'diametro_femoral',
            # Perímetros
            'perimetro_brazo_relajado', 'perimetro_brazo_flexionado', 'perimetro_antebrazo',
            'perimetro_torax', 'perimetro_muslo_superior', 'perimetro_muslo_medial',
            'perimetro_pantorrilla',
            # Pliegues
            'pliegue_tricipital', 'pliegue_subescapular', 'pliegue_supraespinal',
            'pliegue_abdominal', 'pliegue_muslo', 'pliegue_pantorrilla', 'pliegues',
            # Otros
            'peso_ideal_kg', 'observaciones',
        ]
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
            'pliegues': forms.Textarea(attrs={'rows': 2}),
            'observaciones': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_css(self)


class LaboratorioForm(forms.ModelForm):
    class Meta:
        model = Laboratorio
        exclude = ['paciente']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
            'observaciones': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_css(self)


class PlanAlimentarioForm(forms.ModelForm):
    class Meta:
        model = PlanAlimentario
        exclude = ['paciente']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
            'plan_semanal': forms.Textarea(attrs={'rows': 6}),
            'observaciones': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_css(self)


class ConsultaForm(forms.ModelForm):
    class Meta:
        model = Consulta
        exclude = ['paciente']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
            'proximo_turno': forms.DateInput(attrs={'type': 'date'}),
            'observaciones': forms.Textarea(attrs={'rows': 4}),
            'cambios_al_plan': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_css(self)


class TurnoForm(forms.ModelForm):
    class Meta:
        model = Turno
        fields = ['paciente', 'fecha_hora_inicio', 'duracion_minutos', 'motivo', 'estado', 'notas']
        widgets = {
            'fecha_hora_inicio': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
            'notas': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, nutricionista, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['paciente'].queryset = Paciente.objects.filter(
            nutricionista=nutricionista, activo=True
        )
        self.fields['paciente'].required = False
        self.fields['paciente'].empty_label = '--- Sin paciente asignado ---'
        _apply_css(self)
