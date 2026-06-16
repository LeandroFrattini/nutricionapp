from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from .models import Nutricionista, Paciente, Turno
from .emails import enviar_bienvenida


class NutricionistaInline(admin.StackedInline):
    model = Nutricionista
    can_delete = False
    fields = ['matricula', 'especialidad', 'telefono', 'bio', 'aprobado', 'slug']
    readonly_fields = ['slug']


class CustomUserAdmin(UserAdmin):
    inlines = [NutricionistaInline]
    list_display = ['username', 'get_full_name', 'email', 'get_aprobado', 'is_active']
    list_filter = ['is_active', 'nutricionista__aprobado']
    actions = ['aprobar_nutricionistas']

    def get_aprobado(self, obj):
        try:
            return obj.nutricionista.aprobado
        except Nutricionista.DoesNotExist:
            return False
    get_aprobado.boolean = True
    get_aprobado.short_description = 'Aprobado'

    def aprobar_nutricionistas(self, request, queryset):
        for user in queryset:
            try:
                nutri = user.nutricionista
                if not nutri.aprobado:
                    nutri.aprobado = True
                    nutri.save()
                    user.is_active = True
                    user.save()
                    enviar_bienvenida(nutri)
            except Nutricionista.DoesNotExist:
                pass
        self.message_user(request, f'{queryset.count()} nutricionista(s) aprobado(s).')
    aprobar_nutricionistas.short_description = 'Aprobar y activar nutricionistas seleccionados'


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ['apellido', 'nombre', 'nutricionista', 'activo', 'creado_en']
    list_filter = ['activo', 'nutricionista']
    search_fields = ['nombre', 'apellido', 'email']


@admin.register(Turno)
class TurnoAdmin(admin.ModelAdmin):
    list_display = ['fecha_hora_inicio', 'nutricionista', 'paciente', 'duracion_minutos', 'estado']
    list_filter = ['estado', 'nutricionista']
    date_hierarchy = 'fecha_hora_inicio'
