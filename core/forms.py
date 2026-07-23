from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm, SetPasswordForm
from .models import Nutricionista, Paciente, Turno, Medicion, Laboratorio, PlanAlimentario, Consulta, ArchivoPaciente, Pais, CodigoDescuento, Egreso, Provincia, Ciudad

CSS = (
    'w-full px-3 py-2 border border-gray-300 rounded-lg '
    'focus:outline-none focus:ring-2 focus:ring-[#7A5AB4]'
)


def _apply_css(form):
    for field in form.fields.values():
        field.widget.attrs.setdefault('class', CSS)


class LoginForm(AuthenticationForm):
    """Login estándar de Django, pero con el mismo estilo que el resto de los
    formularios — si no, los inputs quedan sin borde ni fondo y se pierden
    contra la card blanca."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_css(self)
        self.fields['username'].label = 'Usuario o email'
        self.fields['username'].widget.attrs['placeholder'] = 'Tu usuario o el email con el que te registraste'
        self.fields['username'].widget.attrs['autofocus'] = True


class EgresoForm(forms.ModelForm):
    class Meta:
        model = Egreso
        fields = ['fecha', 'concepto', 'monto']
        widgets = {'fecha': forms.DateInput(attrs={'type': 'date'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_css(self)


class PasswordChangeStyledForm(PasswordChangeForm):
    """El PasswordChangeForm de Django sin estilos propios — le aplicamos la
    misma clase CSS que al resto de los formularios del dashboard."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_css(self)


class SetPasswordStyledForm(SetPasswordForm):
    """Como PasswordChangeStyledForm, pero sin pedir la contraseña actual —
    para cuando el dueño de la plataforma le pone/cambia la contraseña a un
    nutricionista por él (no hace falta que sepa la vieja)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_css(self)


class RegistroForm(UserCreationForm):
    """Solo lo mínimo para crear la cuenta y cobrar la suscripción — el resto
    del perfil (bio, foto, especialidades, ciudad, obras sociales) se completa
    después desde el dashboard, no hace falta pedirlo acá."""
    first_name = forms.CharField(max_length=100, label='Nombre', required=True)
    last_name = forms.CharField(max_length=100, label='Apellido', required=True)
    email = forms.EmailField(label='Email', required=True)
    matricula = forms.CharField(max_length=50, label='Matricula profesional', required=True)
    pais = forms.ModelChoiceField(
        queryset=Pais.objects.filter(activo=True), label='País', required=True,
        empty_label='— Seleccioná tu país —',
        help_text='Por ahora la plataforma solo está disponible en los países listados.',
    )
    plan_suscripcion = forms.ChoiceField(
        choices=Nutricionista.TIPOS, label='Plan', required=True,
        initial='premium',
        widget=forms.RadioSelect,
    )
    codigo_descuento = forms.CharField(
        max_length=30, label='Código de descuento', required=False,
        help_text='Si tenés uno, escribilo acá — se aplica cuando confirmemos tu suscripción.',
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_css(self)
        self.fields['plan_suscripcion'].widget.attrs.pop('class', None)

    def clean_email(self):
        # Sin esto, nada impedía registrarse varias veces con el mismo email
        # (Django solo exige que el USERNAME sea único) — cada intento crea
        # una cuenta nueva, y el login después no sabe con cuál te referís
        # (ver EmailOrUsernameBackend). iexact porque el login tampoco
        # distingue mayúsculas de minúsculas en el email.
        email = self.cleaned_data['email'].strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Ya hay una cuenta registrada con ese email.')
        return email

    def clean_codigo_descuento(self):
        codigo = self.cleaned_data.get('codigo_descuento', '').strip()
        if not codigo:
            return None
        try:
            return CodigoDescuento.objects.get(codigo__iexact=codigo, activo=True)
        except CodigoDescuento.DoesNotExist:
            raise forms.ValidationError('Ese código no existe o ya no está activo.')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.is_active = False
        if commit:
            user.save()
            nutri = Nutricionista.objects.create(
                user=user,
                matricula=self.cleaned_data['matricula'],
                pais=self.cleaned_data['pais'],
                tipo=self.cleaned_data['plan_suscripcion'],
                codigo_descuento_usado=self.cleaned_data.get('codigo_descuento'),
            )
            if nutri.codigo_descuento_usado:
                from .emails import enviar_aviso_codigo_usado
                try:
                    enviar_aviso_codigo_usado(nutri, nutri.codigo_descuento_usado)
                except Exception:
                    pass
        return user


class PanelNutricionistaCrearForm(forms.Form):
    """Alta manual de un nutricionista desde tu panel — para cuando ya
    arreglaste el pago con alguien y lo querés cargar vos mismo, sin que pase
    por el registro público. Queda aprobado al toque. No le ponemos
    contraseña acá — usa 'Olvidé mi contraseña' para elegir la suya."""
    username = forms.CharField(max_length=150, label='Usuario')
    first_name = forms.CharField(max_length=100, label='Nombre')
    last_name = forms.CharField(max_length=100, label='Apellido')
    email = forms.EmailField(label='Email')
    matricula = forms.CharField(max_length=50, label='Matrícula')
    telefono = forms.CharField(max_length=20, label='Teléfono', required=False)
    pais = forms.ModelChoiceField(
        queryset=Pais.objects.filter(activo=True), label='País', required=False,
        empty_label='— Sin definir —',
    )
    tipo = forms.ChoiceField(choices=Nutricionista.TIPOS, label='Plan', initial='premium')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_css(self)

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Ese usuario ya existe.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email'].strip()
        # iexact, no exact: el login busca el email sin importar mayúsculas
        # (EmailOrUsernameBackend), así que "Nutri@x.com" y "nutri@x.com" son
        # la misma cuenta a todos los efectos — permitir las dos como si
        # fueran distintas solo generaba cuentas duplicadas.
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Ya hay una cuenta con ese email.')
        return email

    def save(self):
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            email=self.cleaned_data['email'],
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
        )
        user.set_unusable_password()
        user.save()
        return Nutricionista.objects.create(
            user=user,
            matricula=self.cleaned_data['matricula'],
            telefono=self.cleaned_data.get('telefono', ''),
            pais=self.cleaned_data.get('pais'),
            tipo=self.cleaned_data['tipo'],
            aprobado=True,
        )


class PanelNutricionistaEditarForm(forms.ModelForm):
    """Edición administrativa desde tu panel — cambiar de plan, frecuencia,
    país, destacado, o dar de baja/alta. No toca bio/foto/especialidades:
    eso lo maneja el nutricionista desde su propio perfil."""
    first_name = forms.CharField(max_length=100, label='Nombre')
    last_name = forms.CharField(max_length=100, label='Apellido')
    email = forms.EmailField(label='Email')

    class Meta:
        model = Nutricionista
        fields = ['matricula', 'telefono', 'pais', 'tipo', 'aprobado', 'destacado', 'exento_de_pago', 'oculto']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        inst = self.instance
        if inst and inst.pk:
            self.initial['first_name'] = inst.user.first_name
            self.initial['last_name'] = inst.user.last_name
            self.initial['email'] = inst.user.email
        _apply_css(self)
        for fname in ['aprobado', 'destacado', 'exento_de_pago', 'oculto']:
            self.fields[fname].widget.attrs.pop('class', None)

    def save(self, commit=True):
        nutri = super().save(commit=False)
        nutri.user.first_name = self.cleaned_data['first_name']
        nutri.user.last_name = self.cleaned_data['last_name']
        nutri.user.email = self.cleaned_data['email']
        nutri.user.is_active = self.cleaned_data['aprobado']
        if commit:
            nutri.user.save()
            nutri.save()
        return nutri


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
    composicion_corporal = forms.MultipleChoiceField(
        choices=Nutricionista.COMPOSICION_CORPORAL,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Composición corporal',
    )
    modalidad = forms.ChoiceField(
        choices=Nutricionista.MODALIDADES,
        widget=forms.RadioSelect,
        required=False,
        label='Modalidad de atención',
    )
    provincia = forms.ModelChoiceField(
        queryset=Provincia.objects.none(), required=False, label='Provincia',
        empty_label='— Seleccioná tu provincia —',
        help_text='Elegí la provincia primero para que se carguen las ciudades.',
    )

    class Meta:
        model = Nutricionista
        fields = [
            'foto', 'matricula', 'telefono', 'bio',
            'ciudad', 'obras_sociales', 'acepta_obras_sociales',
            'especialidad_otra', 'mensaje_recordatorio',
        ]
        labels = {
            'foto': 'Foto de perfil',
            'matricula': 'Matrícula',
            'telefono': 'Teléfono',
            'bio': 'Sobre mí (texto que ven los pacientes)',
            'ciudad': 'Ciudad',
            'obras_sociales': 'Obras sociales que aceptás',
            'acepta_obras_sociales': 'Acepto obras sociales',
            'especialidad_otra': '¿Cuál?',
            'mensaje_recordatorio': 'Mensaje de recordatorio por WhatsApp',
        }
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
            'obras_sociales': forms.CheckboxSelectMultiple,
            'especialidad_otra': forms.TextInput(attrs={'placeholder': 'Ej: Nutrición oncológica'}),
            'mensaje_recordatorio': forms.Textarea(attrs={'rows': 3, 'placeholder': Nutricionista.MENSAJE_RECORDATORIO_DEFAULT}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        inst = self.instance
        provincia_actual = None
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
            self.initial['composicion_corporal'] = [
                c.strip() for c in (inst.composicion_corporal or '').split(',') if c.strip()
            ]
            self.initial['modalidad'] = inst.modalidad
            if inst.ciudad and inst.ciudad.provincia:
                provincia_actual = inst.ciudad.provincia
                self.initial['provincia'] = provincia_actual

        # Provincia: solo las del país del nutricionista (si ya lo eligió al
        # registrarse). Ciudad: en la carga inicial, solo las de la provincia
        # ya elegida — el resto de las opciones se cargan solas al cambiar la
        # provincia (ver hx-get más abajo y core/views.py:ciudades_por_provincia).
        provincias_qs = Provincia.objects.filter(activa=True)
        if inst and inst.pais:
            provincias_qs = provincias_qs.filter(pais=inst.pais)
        self.fields['provincia'].queryset = provincias_qs.order_by('nombre')

        # Si el formulario viene con datos posteados (guardando el perfil),
        # la ciudad tiene que validarse contra la provincia QUE SE ELIGIÓ EN
        # ESE ENVÍO — no contra la que ya tenía guardada de antes. Si no, al
        # cambiar de provincia y elegir una ciudad nueva, Django la rechaza
        # por no estar en el queryset viejo.
        provincia_para_ciudad = provincia_actual
        if self.data:
            provincia_posteada = self.data.get('provincia')
            if provincia_posteada:
                provincia_para_ciudad = provincias_qs.filter(pk=provincia_posteada).first()
            else:
                provincia_para_ciudad = None

        if provincia_para_ciudad:
            self.fields['ciudad'].queryset = Ciudad.objects.filter(provincia=provincia_para_ciudad, activa=True).order_by('nombre')
        else:
            self.fields['ciudad'].queryset = Ciudad.objects.none()

        self.fields['provincia'].widget.attrs.update({
            'hx-get': '/perfil/ciudades-por-provincia/',
            'hx-target': '#id_ciudad',
            'hx-trigger': 'change',
            'hx-include': 'this',
        })

        _apply_css(self)
        # Campos que NO deben tener estilos de input de texto
        for fname in ['especialidades', 'edades_atendidas', 'composicion_corporal', 'modalidad',
                      'foto', 'obras_sociales', 'acepta_obras_sociales']:
            if fname in self.fields:
                self.fields[fname].widget.attrs.pop('class', None)
        self.fields['foto'].required = False

    def clean_especialidades(self):
        """Convierte lista → string separado por comas para guardar en CharField."""
        return ','.join(self.cleaned_data.get('especialidades', []))

    def clean_edades_atendidas(self):
        return ','.join(self.cleaned_data.get('edades_atendidas', []))

    def clean_composicion_corporal(self):
        return ','.join(self.cleaned_data.get('composicion_corporal', []))

    def save(self, commit=True):
        nutricionista = super().save(commit=False)
        nutricionista.user.first_name = self.cleaned_data['first_name']
        nutricionista.user.last_name = self.cleaned_data['last_name']
        # Asignar campos declarados que no son parte de Meta.fields
        nutricionista.especialidades = self.cleaned_data.get('especialidades', '')
        nutricionista.edades_atendidas = self.cleaned_data.get('edades_atendidas', '')
        nutricionista.composicion_corporal = self.cleaned_data.get('composicion_corporal', '')
        nutricionista.modalidad = self.cleaned_data.get('modalidad', '')
        if commit:
            nutricionista.user.save()
            nutricionista.save()
            self._save_m2m()
        return nutricionista


class ContactoForm(forms.Form):
    """Pedido liviano de información — mail + WhatsApp opcional. El plan de
    interés viaja aparte (de qué botón vino, ?plan=... en la URL), no se le
    pregunta nada más a la persona para bajar la fricción al mínimo."""
    email = forms.EmailField(label='Email')
    telefono = forms.CharField(label='WhatsApp', required=False, max_length=20)
    plan_interes = forms.ChoiceField(
        choices=[
            ('herramientas', 'Plan Completo — Publicidad + Herramientas'),
            ('publicidad', 'Plan Básico — Solo publicidad'),
            ('sin_definir', 'Todavía no lo decidí'),
        ],
        initial='herramientas',
        widget=forms.HiddenInput,
    )

    def __init__(self, *args, **kwargs):
        plan = kwargs.pop('plan_inicial', None)
        super().__init__(*args, **kwargs)
        if plan and not args:  # solo en formulario vacío
            self.fields['plan_interes'].initial = plan
        _apply_css(self)
        self.fields['plan_interes'].widget.attrs.pop('class', None)


class CodigoDescuentoForm(forms.ModelForm):
    class Meta:
        model = CodigoDescuento
        fields = ['codigo', 'nutricionista_referente', 'porcentaje_descuento', 'activo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['nutricionista_referente'].queryset = Nutricionista.objects.filter(aprobado=True).select_related('user')
        self.fields['nutricionista_referente'].required = False
        _apply_css(self)
        self.fields['activo'].widget.attrs.pop('class', None)

    def clean_codigo(self):
        return self.cleaned_data['codigo'].strip().upper()


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
    Medición básica. Los campos de antropometría ISAK (pliegues, diámetros,
    perímetros) siguen existiendo en el modelo por compatibilidad con datos
    viejos, pero ya no se piden acá — el formulario quedó solo con lo básico.
    """
    class Meta:
        model = Medicion
        fields = [
            'fecha', 'peso_kg', 'altura_cm', 'cintura_cm', 'cadera_cm',
            'peso_ideal_kg', 'observaciones',
        ]
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
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


class ArchivoPacienteForm(forms.ModelForm):
    class Meta:
        model = ArchivoPaciente
        exclude = ['paciente', 'creado_en']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
            'observaciones': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_css(self)
        self.fields['archivo'].widget.attrs['class'] = (
            'w-full text-sm text-gray-600 file:mr-3 file:py-2 file:px-4 file:rounded-lg '
            'file:border-0 file:bg-[#7A5AB4] file:text-white file:font-semibold '
            'file:cursor-pointer hover:file:bg-[#5E4694]'
        )


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
