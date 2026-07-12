"""
Pagos de la suscripción a la plataforma — tanto el pago inicial del registro
como las renovaciones periódicas. Todo pago es un cobro único de Checkout Pro
por la cantidad de meses elegida; al confirmarse, extiende la fecha de
vencimiento esa cantidad de meses y (re)activa la cuenta si estaba
suspendida. No hay cobro automático recurrente de Mercado Pago.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .models import Nutricionista, PagoSuscripcion
from . import mercadopago_suscripciones as mp_susc
from .emails import enviar_bienvenida


def _confirmar_pago(pago):
    """Si el pago fue aprobado en MP y todavía no se había acreditado,
    extiende el vencimiento y (re)activa la cuenta. Devuelve True si lo
    acreditó ahora, False si no hay nada nuevo que hacer."""
    if pago.confirmado:
        return False
    if not mp_susc.pago_fue_aprobado(pago):
        return False
    pago.confirmado = True
    pago.confirmado_en = timezone.now()
    pago.save(update_fields=['confirmado', 'confirmado_en'])

    nutri = pago.nutricionista
    era_primera_vez = not nutri.aprobado
    nutri.extender_vencimiento(pago.meses)
    if not nutri.aprobado:
        nutri.aprobado = True
        nutri.save(update_fields=['aprobado'])
    if era_primera_vez:
        try:
            enviar_bienvenida(nutri)
        except Exception:
            pass
    return True


def registro_pagar(request, pk):
    """Apenas termina el registro, genera el cobro del primer mes (con
    descuento si usó código de descuento) y redirige a pagarlo."""
    nutri = get_object_or_404(Nutricionista, pk=pk)

    if not mp_susc.configurado():
        return render(request, 'registration/pago_pendiente_manual.html', {'nutri': nutri})

    monto = mp_susc.monto_por_meses(nutri.tipo, 1, nutri.codigo_descuento_usado)
    pago = PagoSuscripcion.objects.create(nutricionista=nutri, meses=1, monto=monto)
    link = mp_susc.crear_pago(pago, f'NutricionClick — primer mes ({nutri.get_tipo_display()})')
    if not link:
        return render(request, 'registration/pago_pendiente_manual.html', {'nutri': nutri})
    return redirect(link)


def pago_retorno(request, pago_pk):
    """A donde vuelve el profesional después de pagar (registro o
    renovación). Sirve para ambos casos: si es el primer pago confirmado de
    la cuenta, muestra la pantalla de bienvenida; si no, una de renovación."""
    pago = get_object_or_404(PagoSuscripcion, pk=pago_pk)
    ya_habia_pagos_confirmados = PagoSuscripcion.objects.filter(
        nutricionista=pago.nutricionista, confirmado=True
    ).exclude(pk=pago.pk).exists()

    if pago.confirmado or _confirmar_pago(pago):
        if ya_habia_pagos_confirmados:
            return render(request, 'dashboard/renovar_confirmado.html', {'nutri': pago.nutricionista})
        return render(request, 'registration/pago_ya_confirmado.html', {'nutri': pago.nutricionista})

    return render(request, 'registration/pago_pendiente.html', {'nutri': pago.nutricionista, 'pago': pago})


def mp_webhook_pago(request):
    """Backup del retorno del checkout, por si cierran el navegador antes de
    volver. No confiamos en el contenido de la notificación, solo usamos el
    ID que nosotros mismos pegamos en la notification_url para saber qué pago
    revisar, y volvemos a chequear el estado real contra la API de MP."""
    pago_pk = request.GET.get('pago')
    if not pago_pk:
        return HttpResponse('ok')
    try:
        pago = PagoSuscripcion.objects.get(pk=int(pago_pk))
    except (PagoSuscripcion.DoesNotExist, ValueError):
        return HttpResponse('ok')
    _confirmar_pago(pago)
    return HttpResponse('ok')


def registro_pago_listo(request):
    return render(request, 'registration/pago_listo.html')


@login_required
def renovar(request):
    """Pantalla donde el profesional elige cuántos meses pagar de una vez.
    Ojo: NO usa @nutri_requerido — tiene que ser accesible incluso si la
    cuenta ya está suspendida por falta de pago (si no, no podría pagar para
    reactivarse)."""
    try:
        nutri = request.user.nutricionista
    except Nutricionista.DoesNotExist:
        return redirect('home')
    if not nutri.aprobado:
        return redirect('en_revision')

    if request.method == 'POST':
        try:
            meses = int(request.POST.get('meses', 0))
        except ValueError:
            meses = 0
        if meses not in mp_susc.MESES_DISPONIBLES:
            messages.error(request, 'Elegí una cantidad de meses válida.')
            return redirect('renovar')
        if not mp_susc.configurado():
            messages.error(request, 'Todavía no está disponible el pago automático — escribinos por WhatsApp.')
            return redirect('renovar')
        monto = mp_susc.monto_por_meses(nutri.tipo, meses)
        pago = PagoSuscripcion.objects.create(nutricionista=nutri, meses=meses, monto=monto)
        link = mp_susc.crear_pago(pago, f'NutricionClick — {meses} mes(es) ({nutri.get_tipo_display()})')
        if not link:
            messages.error(request, 'No se pudo generar el link de pago. Escribinos por WhatsApp.')
            return redirect('renovar')
        return redirect(link)

    opciones = []
    for meses in mp_susc.MESES_DISPONIBLES:
        opciones.append({
            'meses': meses,
            'monto': mp_susc.monto_por_meses(nutri.tipo, meses),
            'descuento': mp_susc.DESCUENTOS_VOLUMEN.get(meses, 0),
            'mes_gratis': meses == 12,
        })
    return render(request, 'dashboard/renovar.html', {'nutri': nutri, 'opciones': opciones})


@login_required
def perfil_suspendido(request):
    try:
        nutri = request.user.nutricionista
    except Nutricionista.DoesNotExist:
        return redirect('home')
    dias_venc = nutri.dias_para_vencimiento()
    return render(request, 'dashboard/perfil_suspendido.html', {
        'nutri': nutri,
        'dias_vencido_abs': abs(dias_venc) if dias_venc is not None else None,
    })
