"""
Portal del paciente: login propio con DNI (usuario y contraseña inicial),
para que el paciente vea y descargue sus archivos cuando quiera, sin
depender de que el nutricionista le reenvíe el link por WhatsApp cada vez.

No usa el sistema de auth de Django (User/login_required) — es un login
aparte, con su propia sesión, porque el mismo DNI puede repetirse entre las
carteras de pacientes de dos nutricionistas distintos (User.username tiene
que ser único en todo el sitio, y acá no queremos esa restricción).
"""
from functools import wraps

from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages

from .models import Paciente

INTENTOS_MAXIMOS = 5
BLOQUEO_MINUTOS = 15


def _cache_key(request, dni):
    ip = request.META.get('REMOTE_ADDR', 'sin-ip')
    return f'portal_login_intentos:{ip}:{dni}'


def _bloqueado(request, dni):
    return cache.get(_cache_key(request, dni), 0) >= INTENTOS_MAXIMOS


def _registrar_intento_fallido(request, dni):
    key = _cache_key(request, dni)
    intentos = cache.get(key, 0) + 1
    cache.set(key, intentos, timeout=BLOQUEO_MINUTOS * 60)


def _limpiar_intentos(request, dni):
    cache.delete(_cache_key(request, dni))


def paciente_portal_requerido(view_func):
    """Exige que haya un paciente logueado en la sesión del portal."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        paciente_id = request.session.get('portal_paciente_id')
        if not paciente_id:
            return redirect('portal_login')
        try:
            paciente = Paciente.objects.get(pk=paciente_id, activo=True)
        except Paciente.DoesNotExist:
            request.session.flush()
            return redirect('portal_login')
        return view_func(request, paciente, *args, **kwargs)
    return wrapper


def portal_login(request):
    if request.session.get('portal_paciente_id'):
        return redirect('portal_dashboard')

    error = None
    if request.method == 'POST':
        # El DNI se guarda normalizado (solo dígitos) — aceptamos que lo
        # tipeen con puntos o espacios ("30.123.456") igual que sin ellos.
        dni = ''.join(c for c in request.POST.get('dni', '') if c.isdigit())
        password_crudo = request.POST.get('password', '')
        password_normalizado = ''.join(c for c in password_crudo if c.isdigit())

        if _bloqueado(request, dni):
            error = f'Demasiados intentos fallidos. Probá de nuevo en {BLOQUEO_MINUTOS} minutos.'
        elif dni and password_crudo:
            candidatos = [
                p for p in Paciente.objects.filter(dni=dni, activo=True).select_related('nutricionista__user')
                # La contraseña inicial ES el DNI (ver mensaje en el detalle
                # del paciente) — si todavía no la cambió, aceptamos que la
                # haya tipeado con la misma puntuación "humana" que el DNI.
                if check_password(password_crudo, p.portal_password)
                or (p.portal_debe_cambiar_password and password_normalizado
                    and check_password(password_normalizado, p.portal_password))
            ]
            if not candidatos:
                _registrar_intento_fallido(request, dni)
                error = 'DNI o contraseña incorrectos.'
            elif len(candidatos) == 1:
                _limpiar_intentos(request, dni)
                request.session['portal_paciente_id'] = candidatos[0].pk
                return redirect('portal_dashboard')
            else:
                # El mismo DNI existe en la cartera de más de un nutricionista
                # (paciente que atienden dos profesionales distintos) — no
                # hay forma de saber cuál quiere ver sin preguntarle.
                _limpiar_intentos(request, dni)
                request.session['portal_candidatos'] = [p.pk for p in candidatos]
                return redirect('portal_seleccionar_perfil')
        else:
            error = 'Completá DNI y contraseña.'

    return render(request, 'portal/login.html', {'error': error})


def portal_seleccionar_perfil(request):
    ids = request.session.get('portal_candidatos') or []
    candidatos = Paciente.objects.filter(pk__in=ids, activo=True).select_related('nutricionista__user')
    if not candidatos:
        return redirect('portal_login')

    if request.method == 'POST':
        elegido_id = request.POST.get('paciente_id')
        if elegido_id and int(elegido_id) in ids:
            del request.session['portal_candidatos']
            request.session['portal_paciente_id'] = int(elegido_id)
            return redirect('portal_dashboard')

    return render(request, 'portal/seleccionar_perfil.html', {'candidatos': candidatos})


def portal_logout(request):
    request.session.flush()
    return redirect('portal_login')


@paciente_portal_requerido
def portal_cambiar_password(request, paciente):
    error = None
    if request.method == 'POST':
        nueva1 = request.POST.get('nueva1', '')
        nueva2 = request.POST.get('nueva2', '')
        if len(nueva1) < 4:
            error = 'La contraseña tiene que tener al menos 4 caracteres.'
        elif nueva1 != nueva2:
            error = 'Las contraseñas no coinciden.'
        else:
            paciente.portal_password = make_password(nueva1)
            paciente.portal_debe_cambiar_password = False
            paciente.save(update_fields=['portal_password', 'portal_debe_cambiar_password'])
            messages.success(request, 'Contraseña actualizada.')
            return redirect('portal_dashboard')
    return render(request, 'portal/cambiar_password.html', {'paciente': paciente, 'error': error})


@paciente_portal_requerido
def portal_dashboard(request, paciente):
    if paciente.portal_debe_cambiar_password:
        return redirect('portal_cambiar_password')
    archivos = paciente.archivos.all()
    return render(request, 'portal/dashboard.html', {'paciente': paciente, 'archivos': archivos})
