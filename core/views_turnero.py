"""
Turnero online: configuracion del nutricionista, reserva publica de
pacientes, seña por Mercado Pago y recordatorios.
"""
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import emails, mercadopago
from .models import (BloqueoFecha, ConfiguracionTurnero, FranjaHoraria,
                     Nutricionista, Paciente, Turno)


def _get_turnero(request):
    nutri = get_object_or_404(
        Nutricionista, user=request.user, tipo='premium', aprobado=True
    )
    turnero, _ = ConfiguracionTurnero.objects.get_or_create(nutricionista=nutri)
    return nutri, turnero


def _link_publico(request, nutri):
    return request.build_absolute_uri(
        reverse('turnero_reservar', kwargs={'slug': nutri.slug})
    )


# ═════════════════════════════════════════════════════════════════════════
# DASHBOARD DEL NUTRICIONISTA
# ═════════════════════════════════════════════════════════════════════════

@login_required
def turnero_config(request):
    nutri, turnero = _get_turnero(request)

    if request.method == 'POST' and request.POST.get('accion') == 'guardar_config':
        turnero.activo = request.POST.get('activo') == 'on'
        turnero.requiere_sena = request.POST.get('requiere_sena') == 'on'
        try:
            turnero.duracion_turno_minutos = max(10, min(180, int(request.POST.get('duracion_turno_minutos', 30))))
            turnero.porcentaje_sena = max(1, min(100, int(request.POST.get('porcentaje_sena', 50))))
            turnero.horas_recordatorio = max(2, min(96, int(request.POST.get('horas_recordatorio', 24))))
            turnero.horas_limite_pago = max(1, min(48, int(request.POST.get('horas_limite_pago', 6))))
            turnero.anticipacion_maxima_dias = max(1, min(90, int(request.POST.get('anticipacion_maxima_dias', 30))))
            precio = request.POST.get('precio_consulta', '').replace(',', '.').strip()
            turnero.precio_consulta = precio or None
        except (ValueError, TypeError):
            messages.error(request, 'Revisa los valores ingresados.')
            return redirect('turnero_config')
        turnero.save()
        messages.success(request, 'Configuracion del turnero guardada.')
        return redirect('turnero_config')

    dias_con_franjas = []
    franjas_por_dia = {d: [] for d, _ in FranjaHoraria.DIAS}
    for f in turnero.franjas.all():
        franjas_por_dia[f.dia_semana].append(f)
    for dia_num, dia_nombre in FranjaHoraria.DIAS:
        dias_con_franjas.append({
            'num': dia_num,
            'nombre': dia_nombre,
            'franjas': franjas_por_dia[dia_num],
        })

    return render(request, 'turnero/configuracion.html', {
        'nutri': nutri,
        'turnero': turnero,
        'dias_con_franjas': dias_con_franjas,
        'bloqueos': turnero.bloqueos.filter(fecha_hasta__gte=date.today()),
        'link_publico': _link_publico(request, nutri),
        'mp_configurado': bool(getattr(settings, 'MP_APP_ID', '')),
    })


@login_required
@require_POST
def franja_agregar(request):
    nutri, turnero = _get_turnero(request)
    try:
        dia = int(request.POST['dia_semana'])
        hora_inicio = time.fromisoformat(request.POST['hora_inicio'])
        hora_fin = time.fromisoformat(request.POST['hora_fin'])
    except (KeyError, ValueError):
        messages.error(request, 'Horario invalido.')
        return redirect('turnero_config')

    if hora_fin <= hora_inicio:
        messages.error(request, 'La hora "hasta" tiene que ser mayor que la hora "desde".')
        return redirect('turnero_config')

    solapada = turnero.franjas.filter(
        dia_semana=dia, hora_inicio__lt=hora_fin, hora_fin__gt=hora_inicio
    ).exists()
    if solapada:
        messages.error(request, 'Esa franja se superpone con otra que ya cargaste para ese dia.')
        return redirect('turnero_config')

    FranjaHoraria.objects.create(
        turnero=turnero, dia_semana=dia, hora_inicio=hora_inicio, hora_fin=hora_fin
    )
    messages.success(request, 'Franja horaria agregada.')
    return redirect('turnero_config')


@login_required
@require_POST
def franja_eliminar(request, pk):
    nutri, turnero = _get_turnero(request)
    franja = get_object_or_404(FranjaHoraria, pk=pk, turnero=turnero)
    franja.delete()
    messages.success(request, 'Franja eliminada.')
    return redirect('turnero_config')


@login_required
@require_POST
def bloqueo_agregar(request):
    nutri, turnero = _get_turnero(request)
    try:
        desde = date.fromisoformat(request.POST['fecha_desde'])
        hasta = date.fromisoformat(request.POST.get('fecha_hasta') or request.POST['fecha_desde'])
    except (KeyError, ValueError):
        messages.error(request, 'Fecha invalida.')
        return redirect('turnero_config')
    if hasta < desde:
        desde, hasta = hasta, desde
    BloqueoFecha.objects.create(
        turnero=turnero, fecha_desde=desde, fecha_hasta=hasta,
        motivo=request.POST.get('motivo', '')[:100],
    )
    messages.success(request, 'Fechas bloqueadas.')
    return redirect('turnero_config')


@login_required
@require_POST
def bloqueo_eliminar(request, pk):
    nutri, turnero = _get_turnero(request)
    bloqueo = get_object_or_404(BloqueoFecha, pk=pk, turnero=turnero)
    bloqueo.delete()
    messages.success(request, 'Bloqueo eliminado.')
    return redirect('turnero_config')


# ─── Vinculacion Mercado Pago ─────────────────────────────────────────────

@login_required
def mp_conectar(request):
    nutri, turnero = _get_turnero(request)
    if not getattr(settings, 'MP_APP_ID', ''):
        messages.error(request, 'Mercado Pago no esta configurado en la plataforma todavia.')
        return redirect('turnero_config')
    return redirect(mercadopago.url_autorizacion(nutri))


@login_required
def mp_callback(request):
    nutri, turnero = _get_turnero(request)
    code = request.GET.get('code')
    if not code:
        messages.error(request, 'Mercado Pago no devolvio la autorizacion. Proba de nuevo.')
        return redirect('turnero_config')
    data = mercadopago.intercambiar_codigo(code)
    if not data or not data.get('access_token'):
        messages.error(request, 'No pudimos vincular tu cuenta de Mercado Pago. Proba de nuevo.')
        return redirect('turnero_config')
    mercadopago.guardar_tokens(turnero, data)
    messages.success(request, '¡Cuenta de Mercado Pago vinculada! Las señas van a llegar directo a tu cuenta.')
    return redirect('turnero_config')


@login_required
@require_POST
def mp_desconectar(request):
    nutri, turnero = _get_turnero(request)
    mercadopago.desconectar(turnero)
    messages.success(request, 'Cuenta de Mercado Pago desvinculada.')
    return redirect('turnero_config')


# ═════════════════════════════════════════════════════════════════════════
# RESERVA PUBLICA (el paciente, sin login)
# ═════════════════════════════════════════════════════════════════════════

@never_cache
def turnero_reservar(request, slug):
    nutri = get_object_or_404(
        Nutricionista, slug=slug, aprobado=True, user__is_active=True
    )
    turnero = getattr(nutri, 'turnero', None)
    if not turnero or not turnero.activo or not turnero.listo_para_publicar:
        return render(request, 'turnero/no_disponible.html', {'nutri': nutri}, status=404)

    hoy = timezone.localdate()
    dias = []
    for i in range(turnero.anticipacion_maxima_dias + 1):
        d = hoy + timedelta(days=i)
        slots = turnero.generar_slots(d)
        if slots:
            dias.append({'fecha': d, 'slots': slots})
        if len(dias) >= 14:  # mostramos hasta 14 dias con disponibilidad
            break

    fecha_sel = request.GET.get('fecha')
    dia_activo = None
    if fecha_sel:
        for d in dias:
            if d['fecha'].isoformat() == fecha_sel:
                dia_activo = d
                break
    if dia_activo is None and dias:
        dia_activo = dias[0]

    if request.method == 'POST':
        return _crear_reserva(request, nutri, turnero)

    return render(request, 'turnero/reservar.html', {
        'nutri': nutri,
        'turnero': turnero,
        'dias': dias,
        'dia_activo': dia_activo,
    })


def _crear_reserva(request, nutri, turnero):
    nombre = request.POST.get('nombre', '').strip()[:100]
    apellido = request.POST.get('apellido', '').strip()[:100]
    email = request.POST.get('email', '').strip()[:200]
    telefono = request.POST.get('telefono', '').strip()[:30]
    motivo = request.POST.get('motivo', '').strip()[:200]
    slot_str = request.POST.get('slot', '')

    if not (nombre and apellido and email and slot_str):
        messages.error(request, 'Completa tu nombre, apellido, email y elegi un horario.')
        return redirect('turnero_reservar', slug=nutri.slug)

    try:
        slot = datetime.fromisoformat(slot_str)
        if timezone.is_naive(slot):
            slot = timezone.make_aware(slot)
    except ValueError:
        messages.error(request, 'Horario invalido.')
        return redirect('turnero_reservar', slug=nutri.slug)

    # Validar que el slot siga disponible (evita dobles reservas)
    disponibles = turnero.generar_slots(slot.date())
    if slot not in disponibles:
        messages.error(request, 'Ese horario acaba de ocuparse. Elegi otro, por favor.')
        return redirect('turnero_reservar', slug=nutri.slug)

    # Si el email coincide con un paciente existente, lo vinculamos
    paciente = Paciente.objects.filter(
        nutricionista=nutri, email__iexact=email
    ).first() if email else None

    turno = Turno.objects.create(
        nutricionista=nutri,
        paciente=paciente,
        fecha_hora_inicio=slot,
        duracion_minutos=turnero.duracion_turno_minutos,
        estado='pendiente',
        motivo=motivo,
        origen='online',
        nombre_contacto=nombre,
        apellido_contacto=apellido,
        email_contacto=email,
        telefono_contacto=telefono,
        sena_monto=turnero.monto_sena if turnero.requiere_sena else None,
    )

    if not turnero.requiere_sena:
        turno.estado = 'confirmado'
        turno.save(update_fields=['estado'])
        emails.enviar_reserva_online(turno, turnero)
    else:
        horas_hasta_turno = (slot - timezone.now()).total_seconds() / 3600
        if horas_hasta_turno <= turnero.horas_recordatorio:
            # El turno es pronto: pedimos la seña ya mismo
            _solicitar_sena(request, turno, turnero)
        emails.enviar_reserva_online(turno, turnero)

    return redirect('turnero_reservado', token=turno.token)


def _solicitar_sena(request, turno, turnero):
    """Pasa el turno a 'esperando seña' y envia el mail con link de pago."""
    turno.estado = 'pendiente_sena'
    turno.recordatorio_enviado_en = timezone.now()
    turno.save(update_fields=['estado', 'recordatorio_enviado_en'])
    link_pago = request.build_absolute_uri(
        reverse('turnero_pagar', kwargs={'token': turno.token})
    ) if request else settings.SITE_URL.rstrip('/') + reverse(
        'turnero_pagar', kwargs={'token': turno.token}
    )
    emails.enviar_recordatorio_sena(turno, turnero, link_pago)


def turnero_reservado(request, token):
    """Pagina de estado del turno para el paciente (sin login)."""
    turno = get_object_or_404(Turno, token=token)
    turnero = getattr(turno.nutricionista, 'turnero', None)
    return render(request, 'turnero/reservado.html', {
        'turno': turno,
        'turnero': turnero,
        'nutri': turno.nutricionista,
    })


def turnero_pagar(request, token):
    """Genera la preferencia de MP y redirige al checkout."""
    turno = get_object_or_404(Turno, token=token)
    turnero = getattr(turno.nutricionista, 'turnero', None)

    if turno.sena_pagada or turno.estado == 'confirmado':
        messages.success(request, 'Tu turno ya esta confirmado. ¡No hace falta pagar de nuevo!')
        return redirect('turnero_reservado', token=turno.token)
    if turno.estado in ('cancelado', 'vencido') or not turnero or not turno.sena_monto:
        messages.error(request, 'Este turno ya no admite pago de seña.')
        return redirect('turnero_reservado', token=turno.token)

    init_point = mercadopago.crear_preferencia_sena(turno, turnero)
    if not init_point:
        messages.error(request, 'No pudimos generar el link de pago. Proba de nuevo en unos minutos.')
        return redirect('turnero_reservado', token=turno.token)
    return redirect(init_point)


def turnero_pago_retorno(request, token):
    """Vuelta del checkout de MP: verificamos el pago contra la API."""
    turno = get_object_or_404(Turno, token=token)
    turnero = getattr(turno.nutricionista, 'turnero', None)
    _confirmar_si_pagado(turno, turnero)
    return redirect('turnero_reservado', token=turno.token)


@csrf_exempt
def mp_webhook(request):
    """Notificaciones de Mercado Pago (backup del retorno del checkout)."""
    token = request.GET.get('turno')
    if not token:
        return HttpResponse('ok')
    try:
        turno = Turno.objects.get(token=token)
    except (Turno.DoesNotExist, ValueError):
        return HttpResponse('ok')
    turnero = getattr(turno.nutricionista, 'turnero', None)
    _confirmar_si_pagado(turno, turnero)
    return HttpResponse('ok')


def _confirmar_si_pagado(turno, turnero):
    if turno.sena_pagada or not turnero:
        return
    payment_id = mercadopago.verificar_pago_turno(turno, turnero)
    if payment_id:
        turno.sena_pagada = True
        turno.sena_pagada_en = timezone.now()
        turno.mp_payment_id = payment_id
        turno.estado = 'confirmado'
        turno.save(update_fields=['sena_pagada', 'sena_pagada_en', 'mp_payment_id', 'estado'])
        emails.enviar_sena_confirmada(turno, turnero)


def turnero_cancelar_publico(request, token):
    """El paciente cancela su turno desde el link del mail."""
    turno = get_object_or_404(Turno, token=token)
    if request.method == 'POST':
        if turno.estado in ('pendiente', 'pendiente_sena', 'confirmado'):
            turno.estado = 'cancelado'
            turno.save(update_fields=['estado'])
            messages.success(request, 'Tu turno fue cancelado.')
        return redirect('turnero_reservado', token=turno.token)
    return render(request, 'turnero/cancelar.html', {
        'turno': turno, 'nutri': turno.nutricionista,
    })


def turno_confirmar_publico(request, token):
    """El paciente confirma que va a venir, desde el link del recordatorio
    de WhatsApp. Pensado sobre todo para nutricionistas que no piden seña
    online — hasta ahora no tenían ninguna forma de que el paciente confirme
    asistencia. Exige POST (no confirma solo con el GET) para que no lo
    dispare el preview automático de un link que hacen WhatsApp/Facebook al
    generar la vista previa del mensaje."""
    turno = get_object_or_404(Turno, token=token)
    if request.method == 'POST' and turno.estado == 'pendiente':
        turno.estado = 'confirmado'
        turno.save(update_fields=['estado'])
        return redirect('turno_confirmar_publico', token=turno.token)
    return render(request, 'turnero/confirmar.html', {
        'turno': turno, 'nutri': turno.nutricionista,
    })
