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

    class Meta:
        model = Nutricionista
        fields = ['especialidades', 'matricula', 'telefono', 'bio']
        labels = {
            'especialidades': 'Especialidades',
            'matricula': 'Matricula',
            'telefono': 'Telefono',
            'bio': 'Biografia',
        }
        widgets = {'bio': forms.Textarea(attrs={'rows': 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user_id:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
        _apply_css(self)

    def save(self, commit=True):
        nutricionista = super().save(commit=False)
        nutricionista.user.first_name = self.cleaned_data['first_name']
        nutricionista.user.last_name = self.cleaned_data['last_name']
        if commit:
            nutricionista.user.save()
            nutricionista.save()
        return nutricionista


class ContactoForm(forms.Form):
    nombre = forms.CharField(max_length=100, label='Nombre')
    apellido = forms.CharField(max_length=100, label='Apellido')
    email = forms.EmailField(label='Email')
    telefono = forms.CharField(max_length=20, label='Telefono', required=False)
    plan_interes = forms.ChoiceField(
        choices=[
            ('publicidad', 'Solo publicidad (perfil en web e Instagram)'),
            ('herramientas', 'Publicidad + Herramientas (turnero, pacientes, etc.)'),
            ('sin_definir', 'Todavia no lo decidi'),
        ],
        label='Que plan te interesa?'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_css(self)


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
    class Meta:
        model = Medicion
        exclude = ['paciente']
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
