"""
Panel del dueño de la plataforma (vos) — separado del admin de Django y del
dashboard de cada nutricionista. Acceso solo para superusuarios.
"""
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404

import base64
import mimetypes
from datetime import date

from .models import Nutricionista, Paciente, ContactoInteresado, CodigoDescuento, Egreso
from .utils import superuser_requerido
from .forms import (
    CodigoDescuentoForm, PanelNutricionistaCrearForm, PanelNutricionistaEditarForm,
    EgresoForm, SetPasswordStyledForm,
)

# Precios actuales — mantené esto sincronizado con templates/emails/planes_info.html
# y core/mercadopago_suscripciones.py si cambian. Es un valor para ESTIMAR
# ingresos, no reemplaza mirar Mercado Pago para saber si alguien pagó de verdad.
PRECIO_MENSUAL = {'base': 15000, 'premium': 40000}

# % que se queda Mercado Pago por cada cobro — se descuenta SOLO acá, para tu
# propio control de ganancia real. Los nutricionistas siguen viendo y pagando
# el precio de lista completo (esto no les afecta el monto a ellos).
COMISION_MERCADO_PAGO = 7.99


def _ingreso_mensual_estimado(nutri):
    """Usa el ÚLTIMO pago CONFIRMADO de verdad (monto / meses pagados) en vez
    del precio de lista fijo — si no, un código de descuento (que solo se
    aplica al primer mes) o un pago de varios meses con descuento por volumen
    quedaban invisibles acá, mostrando siempre el precio de lista completo
    aunque se haya cobrado menos."""
    if nutri.exento_de_pago:
        return 0
    ultimo_pago = nutri.pagos_suscripcion.filter(confirmado=True).order_by('-confirmado_en').first()
    if ultimo_pago:
        return round(float(ultimo_pago.monto) / ultimo_pago.meses, 2)
    return PRECIO_MENSUAL.get(nutri.tipo, 0)


@login_required
@superuser_requerido
def panel_resumen(request):
    if request.method == 'POST':
        form = EgresoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Egreso cargado.')
            return redirect('panel_resumen')
    else:
        form = EgresoForm()

    activos = Nutricionista.objects.filter(aprobado=True, oculto=False)
    ingreso_estimado_bruto = sum(_ingreso_mensual_estimado(n) for n in activos)
    ingreso_estimado = round(ingreso_estimado_bruto * (1 - COMISION_MERCADO_PAGO / 100), 2)

    hoy = date.today()
    egresos_mes = Egreso.objects.filter(fecha__year=hoy.year, fecha__month=hoy.month)
    total_egresos_mes = sum(e.monto for e in egresos_mes)

    return render(request, 'panel/resumen.html', {
        'total_activos': activos.count(),
        'total_premium': activos.filter(tipo='premium').count(),
        'total_base': activos.filter(tipo='base').count(),
        'total_pendientes': Nutricionista.objects.filter(aprobado=False).count(),
        'total_pacientes': Paciente.objects.filter(activo=True).count(),
        'total_leads_sin_contactar': ContactoInteresado.objects.filter(contactado=False).count(),
        'total_codigos_activos': CodigoDescuento.objects.filter(activo=True).count(),
        'ingreso_estimado': ingreso_estimado,
        'ingreso_estimado_bruto': ingreso_estimado_bruto,
        'comision_mp': COMISION_MERCADO_PAGO,
        'egresos_mes': egresos_mes,
        'total_egresos_mes': total_egresos_mes,
        # total_egresos_mes es Decimal (viene de sumar Egreso.monto) e
        # ingreso_estimado es float (viene de aplicar la comisión de MP) —
        # Python no permite restar Decimal y float directamente.
        'ganancia_neta_estimada': ingreso_estimado - float(total_egresos_mes),
        'egreso_form': form,
    })


@login_required
@superuser_requerido
def panel_egreso_eliminar(request, pk):
    if request.method == 'POST':
        egreso = get_object_or_404(Egreso, pk=pk)
        egreso.delete()
        messages.success(request, 'Egreso eliminado.')
    return redirect('panel_resumen')


@login_required
@superuser_requerido
def panel_nutricionistas(request):
    q = request.GET.get('q', '').strip()
    qs = Nutricionista.objects.select_related('user', 'pais').order_by('-creado_en')
    if q:
        from django.db.models import Q
        qs = qs.filter(Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q) | Q(user__email__icontains=q))
    return render(request, 'panel/nutricionistas.html', {'nutricionistas': qs, 'q': q})


@login_required
@superuser_requerido
def panel_nutricionista_toggle_aprobado(request, pk):
    if request.method == 'POST':
        nutri = get_object_or_404(Nutricionista, pk=pk)
        nutri.aprobado = not nutri.aprobado
        nutri.user.is_active = nutri.aprobado
        nutri.user.save(update_fields=['is_active'])
        nutri.save(update_fields=['aprobado'])
        # Si se aprueba a mano (p.ej. no pudo completar el pago por el sitio
        # y se le activo la cuenta manualmente) y todavia no tiene ningun
        # vencimiento cargado, le damos el mismo primer mes que le daria un
        # pago normal confirmado por Mercado Pago — si no, quedaba aprobada
        # para siempre sin vencimiento y nunca iba a aparecer como vencida.
        # Las cuentas exentas de pago no necesitan esto.
        if nutri.aprobado and not nutri.exento_de_pago and not nutri.proxima_revision_pago:
            nutri.extender_vencimiento(1)
        estado = 'aprobado' if nutri.aprobado else 'dado de baja'
        messages.success(request, f'{nutri.user.get_full_name()} — {estado}.')
    return redirect('panel_nutricionistas')


@login_required
@superuser_requerido
def panel_nutricionista_eliminar(request, pk):
    """Borra por completo la cuenta (y en cascada TODO lo asociado: pacientes,
    turnos, mediciones, pagos, etc.) — pensado para registros duplicados o
    de prueba que nunca llegaron a usarse de verdad. Antes esto solo se podía
    hacer desde /admin/, no había forma desde el panel normal."""
    nutri = get_object_or_404(Nutricionista, pk=pk)
    if request.method == 'POST':
        nombre = nutri.user.get_full_name() or nutri.user.username
        nutri.user.delete()  # el Nutricionista se borra solo por el CASCADE del OneToOne
        messages.success(request, f'{nombre} — cuenta eliminada por completo.')
    return redirect('panel_nutricionistas')


@login_required
@superuser_requerido
def panel_reparar_logins(request):
    """Corrige de una sola vez a los nutricionistas que quedaron con datos
    inconsistentes por bugs ya corregidos (o por haber sido aprobados a
    mano antes de que existiera el fix correspondiente):

    1. Aprobados pero con el login roto (el pago automático de Mercado Pago
       aprobaba la cuenta pero nunca activaba el usuario de Django).
    2. Aprobados, no exentos de pago, pero sin ningún vencimiento cargado
       (quedaban aprobados para siempre sin vencer nunca — pasaba al
       aprobar a mano a alguien que no pudo pagar por el sitio)."""
    if request.method == 'POST':
        sin_login = Nutricionista.objects.filter(aprobado=True, user__is_active=False)
        nombres_login = [n.user.get_full_name() or n.user.username for n in sin_login]
        for nutri in sin_login:
            nutri.user.is_active = True
            nutri.user.save(update_fields=['is_active'])

        sin_vencimiento = Nutricionista.objects.filter(
            aprobado=True, exento_de_pago=False, proxima_revision_pago__isnull=True,
        )
        nombres_vencimiento = [n.user.get_full_name() or n.user.username for n in sin_vencimiento]
        for nutri in sin_vencimiento:
            nutri.extender_vencimiento(1)

        partes = []
        if nombres_login:
            partes.append(f'{len(nombres_login)} cuenta(s) con login roto ({", ".join(nombres_login)})')
        if nombres_vencimiento:
            partes.append(f'{len(nombres_vencimiento)} cuenta(s) sin vencimiento ({", ".join(nombres_vencimiento)})')
        if partes:
            messages.success(request, 'Se repararon: ' + '; '.join(partes) + '.')
        else:
            messages.info(request, 'No había ninguna cuenta con esos problemas — todo en orden.')
    return redirect('panel_nutricionistas')


@login_required
@superuser_requerido
def panel_nutricionista_toggle_destacado(request, pk):
    if request.method == 'POST':
        nutri = get_object_or_404(Nutricionista, pk=pk)
        nutri.destacado = not nutri.destacado
        nutri.save(update_fields=['destacado'])
        estado = 'destacado' if nutri.destacado else 'ya no destacado'
        messages.success(request, f'{nutri.user.get_full_name()} — {estado}.')
    return redirect('panel_nutricionistas')


@login_required
@superuser_requerido
def panel_nutricionista_toggle_exento(request, pk):
    if request.method == 'POST':
        nutri = get_object_or_404(Nutricionista, pk=pk)
        nutri.exento_de_pago = not nutri.exento_de_pago
        nutri.save(update_fields=['exento_de_pago'])
        estado = 'exento de pago' if nutri.exento_de_pago else 'ya no exento de pago'
        messages.success(request, f'{nutri.user.get_full_name()} — {estado}.')
    return redirect('panel_nutricionistas')


@login_required
@superuser_requerido
def panel_nutricionista_nuevo(request):
    if request.method == 'POST':
        form = PanelNutricionistaCrearForm(request.POST)
        if form.is_valid():
            nutri = form.save()
            messages.success(request, f'{nutri.user.get_full_name()} creado y aprobado. Puede entrar usando "Olvidé mi contraseña" con su usuario o email.')
            return redirect('panel_nutricionistas')
    else:
        form = PanelNutricionistaCrearForm()
    return render(request, 'panel/nutricionista_form.html', {'form': form, 'titulo': 'Nuevo nutricionista'})


@login_required
@superuser_requerido
def panel_nutricionista_editar(request, pk):
    nutri = get_object_or_404(Nutricionista, pk=pk)
    if request.method == 'POST':
        form = PanelNutricionistaEditarForm(request.POST, request.FILES, instance=nutri)
        if form.is_valid():
            form.save()
            messages.success(request, f'{nutri.user.get_full_name()} actualizado.')
            return redirect('panel_nutricionistas')
    else:
        form = PanelNutricionistaEditarForm(instance=nutri)
    return render(request, 'panel/nutricionista_form.html', {'form': form, 'titulo': f'Editar — {nutri.user.get_full_name()}', 'nutri': nutri})


@login_required
@superuser_requerido
def panel_nutricionista_cambiar_password(request, pk):
    """Te deja poner o cambiar la contraseña de cualquier nutricionista vos
    mismo, sin depender de que le llegue el mail de "olvidé mi contraseña"
    (útil sobre todo para cuentas que creaste vos mismo con set_unusable_password,
    o si a alguien no le llega el mail por cualquier motivo)."""
    nutri = get_object_or_404(Nutricionista, pk=pk)
    if request.method == 'POST':
        form = SetPasswordStyledForm(nutri.user, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f'Contraseña actualizada para {nutri.user.get_full_name()}.')
            return redirect('panel_nutricionistas')
    else:
        form = SetPasswordStyledForm(nutri.user)
    return render(request, 'panel/nutricionista_cambiar_password.html', {'form': form, 'nutri': nutri})


@login_required
@superuser_requerido
def panel_nutricionista_tarjeta(request, pk):
    """Tarjeta personal descargable (imagen) para que el nutri comparta en
    redes — mismo formato y colores para todos. Se genera solo desde acá
    (vos), no hay botón de autogestión para cada nutri, para no generar
    imágenes de más sin necesidad."""
    nutri = get_object_or_404(Nutricionista, pk=pk)
    foto_b64 = None
    foto_mime = 'image/jpeg'
    if nutri.foto:
        try:
            with nutri.foto.open('rb') as f:
                foto_b64 = base64.b64encode(f.read()).decode('ascii')
            foto_mime = mimetypes.guess_type(nutri.foto.name)[0] or 'image/jpeg'
        except Exception:
            foto_b64 = None
    return render(request, 'panel/nutricionista_tarjeta.html', {
        'nutri': nutri, 'foto_b64': foto_b64, 'foto_mime': foto_mime,
    })


@login_required
@superuser_requerido
def panel_pacientes(request):
    """Listado de TODOS los pacientes de TODOS los nutricionistas — pensado
    solo para poder identificar a alguien por DNI y, si hace falta,
    blanquearle la contraseña del portal (ej. no le llega el mail, se
    equivocó al cambiarla, etc.). No expone ni permite editar datos
    clínicos — para eso está el dashboard del nutricionista."""
    q = request.GET.get('q', '').strip()
    qs = Paciente.objects.select_related('nutricionista__user').order_by('apellido', 'nombre')
    if q:
        from django.db.models import Q
        qs = qs.filter(
            Q(nombre__icontains=q) | Q(apellido__icontains=q) | Q(dni__icontains=q)
            | Q(email__icontains=q) | Q(nutricionista__user__first_name__icontains=q)
            | Q(nutricionista__user__last_name__icontains=q)
        )
    return render(request, 'panel/pacientes.html', {'pacientes': qs, 'q': q})


@login_required
@superuser_requerido
def panel_paciente_blanquear_password(request, pk):
    """Resetea la contraseña del portal al valor por default (su propio
    DNI) y lo obliga a elegir una nueva la próxima vez que entre — mismo
    comportamiento que tiene un paciente recién creado."""
    if request.method == 'POST':
        paciente = get_object_or_404(Paciente, pk=pk)
        if not paciente.dni:
            messages.error(request, f'{paciente.nombre_completo} no tiene DNI cargado — no se puede blanquear.')
        else:
            from django.contrib.auth.hashers import make_password
            paciente.portal_password = make_password(paciente.dni)
            paciente.portal_debe_cambiar_password = True
            paciente.save(update_fields=['portal_password', 'portal_debe_cambiar_password'])
            messages.success(request, f'Contraseña de {paciente.nombre_completo} blanqueada — vuelve a ser su DNI.')
    return redirect('panel_pacientes')


@login_required
@superuser_requerido
def panel_leads(request):
    """Listado de gente que completó "Quiero ser parte" (ContactoInteresado)
    — para hacer seguimiento comercial. Por default muestra solo los que
    todavía no marcaste como contactados."""
    q = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', 'pendientes')
    qs = ContactoInteresado.objects.select_related('pais').order_by('-creado_en')
    if estado == 'pendientes':
        qs = qs.filter(contactado=False)
    if q:
        from django.db.models import Q
        qs = qs.filter(Q(nombre__icontains=q) | Q(apellido__icontains=q) | Q(email__icontains=q))
    return render(request, 'panel/leads.html', {'leads': qs, 'q': q, 'estado': estado})


@login_required
@superuser_requerido
def panel_lead_toggle_contactado(request, pk):
    if request.method == 'POST':
        lead = get_object_or_404(ContactoInteresado, pk=pk)
        lead.contactado = not lead.contactado
        lead.save(update_fields=['contactado'])
        estado = 'contactado' if lead.contactado else 'marcado como pendiente'
        nombre = f'{lead.nombre} {lead.apellido}'.strip() or lead.email
        messages.success(request, f'{nombre} — {estado}.')
    return redirect('panel_leads')


@login_required
@superuser_requerido
def panel_codigos(request):
    hoy = date.today()
    codigos = list(CodigoDescuento.objects.select_related('nutricionista_referente__user').order_by('-creado_en'))
    for c in codigos:
        # c.usos trae TODOS los que cargaron el código al registrarse, pero
        # eso incluye registros abandonados que nunca llegaron a pagar (cada
        # intento de registro crea un Nutricionista nuevo). "Usado" tiene que
        # significar que el pago con ese código se confirmó de verdad.
        c.usados_este_mes = c.usos.filter(
            pagos_suscripcion__confirmado=True,
            pagos_suscripcion__confirmado_en__year=hoy.year,
            pagos_suscripcion__confirmado_en__month=hoy.month,
        ).distinct().count()
        c.activos_totales = c.usos.filter(aprobado=True, pagos_suscripcion__confirmado=True).distinct().count()
    return render(request, 'panel/codigos.html', {'codigos': codigos})


@login_required
@superuser_requerido
def panel_codigo_nuevo(request):
    if request.method == 'POST':
        form = CodigoDescuentoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Código creado.')
            return redirect('panel_codigos')
    else:
        form = CodigoDescuentoForm()
    return render(request, 'panel/codigo_form.html', {'form': form, 'titulo': 'Nuevo código de descuento'})


@login_required
@superuser_requerido
def panel_codigo_editar(request, pk):
    codigo = get_object_or_404(CodigoDescuento, pk=pk)
    if request.method == 'POST':
        form = CodigoDescuentoForm(request.POST, instance=codigo)
        if form.is_valid():
            form.save()
            messages.success(request, 'Código actualizado.')
            return redirect('panel_codigos')
    else:
        form = CodigoDescuentoForm(instance=codigo)
    return render(request, 'panel/codigo_form.html', {'form': form, 'titulo': f'Editar {codigo.codigo}', 'codigo': codigo})
