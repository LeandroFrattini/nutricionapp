import calendar
from functools import wraps
from django.shortcuts import redirect


def sumar_un_mes(fecha):
    """Suma un mes calendario a una fecha/datetime, conservando día y hora.
    Si el mes que viene es más corto (ej. 31 de enero), lo ajusta al último
    día de ese mes en vez de romper (ej. 28/29 de febrero)."""
    mes = fecha.month + 1
    anio = fecha.year + (mes - 1) // 12
    mes = (mes - 1) % 12 + 1
    ultimo_dia_mes = calendar.monthrange(anio, mes)[1]
    dia = min(fecha.day, ultimo_dia_mes)
    return fecha.replace(year=anio, month=mes, day=dia)


def nutri_requerido(view_func):
    """Exige que el usuario logueado tenga un perfil de Nutricionista premium
    y aprobado, e inyecta ese perfil como segundo argumento posicional de la
    vista (justo después de request).

    Si la cuenta existe pero todavía no fue aprobada, redirige a la pantalla
    de 'en revisión' en vez de tirar un 404 crudo — un nutricionista nuevo no
    tiene por qué pensar que la web está rota mientras espera la aprobación
    manual. Se usa siempre junto con @login_required (va debajo).
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from .models import Nutricionista
        try:
            nutri = request.user.nutricionista
        except Nutricionista.DoesNotExist:
            return redirect('home')
        if not nutri.aprobado:
            return redirect('en_revision')
        if nutri.suspendido_por_pago():
            return redirect('perfil_suspendido')
        if nutri.tipo != 'premium':
            return redirect('home')
        return view_func(request, nutri, *args, **kwargs)
    return wrapper


def nutri_requerido_cualquier_plan(view_func):
    """Igual que nutri_requerido, pero sin exigir plan premium — para las
    pocas pantallas que valen para CUALQUIER nutricionista aprobado (hoy:
    solo editar el perfil). El plan básico (solo publicidad) no tiene
    dashboard de herramientas, pero sí tiene que poder cargar su foto/bio/
    especialidades — es literalmente lo único que vende ese plan."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from .models import Nutricionista
        try:
            nutri = request.user.nutricionista
        except Nutricionista.DoesNotExist:
            return redirect('home')
        if not nutri.aprobado:
            return redirect('en_revision')
        if nutri.suspendido_por_pago():
            return redirect('perfil_suspendido')
        return view_func(request, nutri, *args, **kwargs)
    return wrapper


def superuser_requerido(view_func):
    """Exige que el usuario logueado sea superusuario — para el panel del
    dueño de la plataforma (no confundir con nutri_requerido, que es para el
    dashboard de cada nutricionista). Se usa junto con @login_required."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return wrapper


def telefono_whatsapp_ar(telefono):
    """Convierte un teléfono argentino en formato local (ej. '0291 15-4250495',
    con 0 de larga distancia + 15 de celular) al formato que espera wa.me:
    54 + 9 + código de área + número, sin 0 ni 15.

    Es un heurístico (Argentina no tiene códigos de área de largo fijo), pero
    cubre el caso normal: cualquier paciente que se contacte por WhatsApp va
    a tener un número de celular, así que asumimos siempre el prefijo móvil.
    Si el número ya viene en formato internacional (empieza con 54), se deja
    como está.
    """
    digitos = ''.join(c for c in telefono if c.isdigit())
    if not digitos:
        return ''
    if digitos.startswith('54'):
        return digitos
    if digitos.startswith('0'):
        digitos = digitos[1:]
    idx = digitos.find('15')
    if idx != -1:
        digitos = digitos[:idx] + digitos[idx + 2:]
    return '549' + digitos
