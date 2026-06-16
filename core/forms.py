from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Nutricionista, Paciente, Turno


class RegistroForm(UserCreationForm):
    first_name = forms.CharField(max_length=100, label='Nombre', required=True)
    last_name = forms.CharField(max_length=100, label='Apellido', required=True)
    email = forms.EmailField(label='Email', required=True)
    matricula = forms.CharField(max_length=50, label='Matricula profesional', required=True)
    especialidad = forms.ChoiceField(
        choices=[('', '---------')] + Nutricionista.ESPECIALIDADES,
        label='Especialidad', required=False
    )
    telefono = forms.CharField(max_length=20, label='Telefono', required=False)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = (
                'w-full px-3 py-2 border border-gray-300 rounded-lg '
                'focus:outline-none focus:ring-2 focus:ring-green-500'
            )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.is_active = False  # Espera aprobacion del admin
        if commit:
            user.save()
            Nutricionista.objects.create(
                user=user,
                matricula=self.cleaned_data['matricula'],
                especialidad=self.cleaned_data.get('especialidad', ''),
                telefono=self.cleaned_data.get('telefono', ''),
            )
        return user


class PerfilForm(forms.ModelForm):
    first_name = forms.CharField(max_length=100, label='Nombre')
    last_name = forms.CharField(max_length=100, label='Apellido')
    edades_atendidas = forms.MultipleChoiceField(
        choices=Nutricionista.EDADES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Edades que atiende',
    )

    class Meta:
        model = Nutricionista
        fields = [
            'especialidad', 'matricula', 'telefono', 'bio',
            'modalidad', 'acepta_obras_sociales', 'obras_sociales_detalle',
        ]
        labels = {
            'especialidad': 'Especialidad',
            'matricula': 'Matricula',
            'telefono': 'Telefono',
            'bio': 'Biografia',
            'modalidad': 'Modalidad de atencion',
            'acepta_obras_sociales': 'Acepta obras sociales',
            'obras_sociales_detalle': 'Obras sociales (detalle)',
        }
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
            'obras_sociales_detalle': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            # Convertir el string CSV a lista para el MultipleChoiceField
            self.fields['edades_atendidas'].initial = self.instance.get_edades_list()

        input_class = (
            'w-full px-3 py-2 border border-gray-300 rounded-lg '
            'focus:outline-none focus:ring-2 focus:ring-green-500'
        )
        for name, field in self.fields.items():
            if not isinstance(field.widget, (forms.CheckboxSelectMultiple, forms.CheckboxInput)):
                field.widget.attrs['class'] = input_class

    def save(self, commit=True):
        nutricionista = super().save(commit=False)
        # Guardar edades como string CSV
        nutricionista.edades_atendidas = ','.join(self.cleaned_data.get('edades_atendidas', []))
        nutricionista.user.first_name = self.cleaned_data['first_name']
        nutricionista.user.last_name = self.cleaned_data['last_name']
        if commit:
            nutricionista.user.save()
            nutricionista.save()
        return nutricionista


class PacienteForm(forms.ModelForm):
    class Meta:
        model = Paciente
        fields = ['nombre', 'apellido', 'email', 'telefono', 'fecha_nacimiento', 'notas_internas']
        widgets = {
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date'}),
            'notas_internas': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = (
                'w-full px-3 py-2 border border-gray-300 rounded-lg '
                'focus:outline-none focus:ring-2 focus:ring-green-500'
            )


class TurnoForm(forms.ModelForm):
    class Meta:
        model = Turno
        fields = ['paciente', 'fecha_hora_inicio', 'duracion_minutos', 'motivo', 'estado']
        widgets = {
            'fecha_hora_inicio': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
        }

    def __init__(self, nutricionista, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['paciente'].queryset = Paciente.objects.filter(
            nutricionista=nutricionista, activo=True
        )
        self.fields['paciente'].required = False
        self.fields['paciente'].empty_label = '- Sin paciente asignado -'
        for field in self.fields.values():
            field.widget.attrs['class'] = (
                'w-full px-3 py-2 border border-gray-300 rounded-lg '
                'focus:outline-none focus:ring-2 focus:ring-green-500'
            )
