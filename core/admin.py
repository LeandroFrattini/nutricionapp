from django import forms
from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import Nutricionista, Paciente, Turno, Ciudad, ObraSocial, Pais
from .emails import enviar_bienvenida


class NutricionistaAdminForm(forms.ModelForm):
    """Admin form con checkboxes para especialidades y edades (se guardan como string CSV)."""
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
        label='Edades que atiende',
    )

    class Meta:
        model = Nutricionista
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        inst = self.instance
        if inst and inst.pk:
            self.initial['especialidades'] = [
                e.strip() for e in (inst.especialidades or '').split(',') if e.strip()
            ]
            self.initial['edades_atendidas'] = [
                e.strip() for e in (inst.edades_atendidas or '').split(',') if e.strip()
            ]

    def clean_especialidades(self):
        return ','.join(self.cleaned_data.get('especialidades', []))

    def clean_edades_atendidas(self):
        return ','.join(self.cleaned_data.get('edades_atendidas', []))


# ─── CONFIGURACIÓN GENERAL ────────────────────────────────────────────────────
# Solo el superuser (vos) puede acceder al admin.
# Los nutricionistas no son staff, usan solo el dashboard.

admin.site.site_header = "NutricionClick — Panel de administración"
admin.site.site_title = "NutricionClick Admin"
admin.site.index_title = "Panel de control"


# ─── USUARIOS ─────────────────────────────────────────────────────────────────

class CustomUserAdmin(UserAdmin):
    """Gestión básica de acceso. No edites el perfil del nutricionista desde aquí —
    usá el panel de Nutricionistas de abajo."""
    list_display = ['username', 'get_full_name', 'email', 'is_active', 'date_joined']
    list_filter = ['is_active']
    search_fields = ['username', 'first_name', 'last_name', 'email']
    ordering = ['-date_joined']
    # Fieldsets simplificados — sin la lista de permisos granular
    fieldsets = (
        ('Acceso al sistema', {'fields': ('username', 'password')}),
        ('Datos personales', {'fields': ('first_name', 'last_name', 'email')}),
        ('Estado', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'first_name', 'last_name', 'email', 'password1', 'password2'),
        }),
    )


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


# ─── NUTRICIONISTAS ───────────────────────────────────────────────────────────

@admin.register(Nutricionista)
class NutricionistaAdmin(admin.ModelAdmin):
    """Panel principal para gestionar nutricionistas.
    Desde aquí podés aprobar, cambiar el plan, ver la foto y editar el perfil completo."""

    form = NutricionistaAdminForm
    list_display = ['foto_thumb', 'nombre_completo', 'email_usuario', 'matricula', 'ciudad', 'tipo', 'aprobado']
    list_display_links = ['foto_thumb', 'nombre_completo']
    list_filter = ['aprobado', 'tipo', 'ciudad__pais']
    search_fields = ['user__first_name', 'user__last_name', 'user__email', 'matricula']
    list_editable = ['aprobado', 'tipo']
    actions = ['aprobar_y_activar']
    readonly_fields = ['slug', 'foto_preview']

    fieldsets = (
        ('👤 Datos del profesional', {
            'fields': ('user', 'foto', 'foto_preview', 'matricula', 'slug')
        }),
        ('📋 Perfil público', {
            'description': 'Lo que ven los pacientes al buscar un nutricionista.',
            'fields': ('bio', 'especialidades', 'ciudad', 'modalidad', 'edades_atendidas', 'obras_sociales')
        }),
        ('⚙️ Plan y estado', {
            'description': 'Base = solo perfil público. Premium = perfil + dashboard (turnos, pacientes, etc.).',
            'fields': ('tipo', 'aprobado', 'destacado', 'acepta_obras_sociales', 'obras_sociales_detalle')
        }),
    )

    # Columnas de la lista
    def foto_thumb(self, obj):
        if obj.foto:
            return format_html(
                '<img src="{}" style="width:36px;height:36px;border-radius:50%;object-fit:cover;">',
                obj.foto.url
            )
        initials = (obj.user.first_name[:1] + obj.user.last_name[:1]).upper()
        return format_html(
            '<div style="width:36px;height:36px;border-radius:50%;background:#d1fae5;display:flex;'
            'align-items:center;justify-content:center;font-weight:700;color:#065f46;font-size:13px;">{}</div>',
            initials
        )
    foto_thumb.short_description = ''

    def nombre_completo(self, obj):
        return obj.user.get_full_name()
    nombre_completo.short_description = 'Nombre'
    nombre_completo.admin_order_field = 'user__last_name'

    def email_usuario(self, obj):
        return obj.user.email
    email_usuario.short_description = 'Email'

    # Vista previa de foto en el formulario de edición
    def foto_preview(self, obj):
        if obj.foto:
            return format_html(
                '<img src="{}" style="width:100px;height:100px;border-radius:50%;object-fit:cover;'
                'border:2px solid #e5e7eb;margin-top:4px;">',
                obj.foto.url
            )
        return 'Sin foto aún.'
    foto_preview.short_description = 'Vista previa actual'

    # Acción para aprobar
    def aprobar_y_activar(self, request, queryset):
        aprobados = 0
        for nutri in queryset:
            if not nutri.aprobado:
                nutri.aprobado = True
                nutri.save()
                nutri.user.is_active = True
                nutri.user.save()
                try:
                    enviar_bienvenida(nutri)
                except Exception:
                    pass
                aprobados += 1
        self.message_user(request, f'{aprobados} nutricionista(s) aprobado(s) y activado(s).')
    aprobar_y_activar.short_description = '✅ Aprobar y activar seleccionados'


# ─── GEOGRAFÍA ────────────────────────────────────────────────────────────────

@admin.register(Pais)
class PaisAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'codigo', 'activo']
    list_editable = ['activo']
    search_fields = ['nombre']


@admin.register(Ciudad)
class CiudadAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'pais', 'activa']
    list_editable = ['activa']
    list_filter = ['pais']
    search_fields = ['nombre']


@admin.register(ObraSocial)
class ObraSocialAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'activa']
    list_editable = ['activa']
    search_fields = ['nombre']


# ─── PACIENTES Y TURNOS ───────────────────────────────────────────────────────

@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ['apellido', 'nombre', 'nutricionista', 'activo', 'creado_en']
    list_filter = ['activo', 'nutricionista']
    search_fields = ['nombre', 'apellido', 'email']


@admin.register(Turno)
class TurnoAdmin(admin.ModelAdmin):
    list_display = ['fecha_hora_inicio', 'nutricionista', 'paciente', 'estado']
    list_filter = ['estado', 'nutricionista']
    date_hierarchy = 'fecha_hora_inicio'
