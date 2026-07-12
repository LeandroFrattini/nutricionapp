from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone


def _local(fecha_hora):
    """Convierte un DateTimeField (que Django devuelve en UTC al leerlo de la
    base) a la hora local de Argentina antes de formatearlo — si no, todos los
    mails muestran la hora del turno 3 horas adelantada."""
    return timezone.localtime(fecha_hora)


def enviar_alerta_suspension(nutricionistas):
    """Mail interno (a vos, el admin) con la lista de nutricionistas
    suspendidos hoy por falta de pago — para que te comuniques manualmente
    con cada uno si querés. La cuenta ya está bloqueada sola, esto es solo
    para que te enteres."""
    if not nutricionistas:
        return
    lineas = [
        f'{n.user.get_full_name()} ({n.user.email}) — plan {n.get_tipo_display()} — '
        f'vencido hace {abs(n.dias_para_vencimiento())} día(s) (venció el {n.proxima_revision_pago.strftime("%d/%m/%Y")})'
        for n in nutricionistas
    ]
    cuerpo = (
        'Estos nutricionistas están suspendidos por falta de pago (ya sin acceso a su cuenta). '
        'Podés contactarlos si querés hacer seguimiento manual — apenas paguen, se reactivan solos.\n\n'
        + '\n'.join(lineas)
    )
    send_mail(
        subject=f'[NutricionClick] ⛔ {len(nutricionistas)} nutricionista(s) suspendido(s) por falta de pago',
        message=cuerpo,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[settings.ADMIN_EMAIL],
        fail_silently=True,
    )


def enviar_aviso_codigo_usado(nutri_nuevo, codigo):
    """Avisa al nutricionista referente (y a vos) que alguien se registró con
    su código de descuento. El pago del acuerdo entre vos y ese nutricionista
    se maneja aparte — este mail es solo para que se enteren y lo carguen."""
    cuerpo = (
        f'{nutri_nuevo.user.get_full_name()} ({nutri_nuevo.user.email}) se registró en NutricionClick '
        f'usando tu código "{codigo.codigo}" (-{codigo.porcentaje_descuento}%).'
    )
    if codigo.nutricionista_referente and codigo.nutricionista_referente.user.email:
        send_mail(
            subject=f'¡Tu código "{codigo.codigo}" fue usado!',
            message=cuerpo + '\n\nGracias por promocionar NutricionClick.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[codigo.nutricionista_referente.user.email],
            fail_silently=True,
        )
    send_mail(
        subject=f'[NutricionClick] Código "{codigo.codigo}" usado — avisar al referente',
        message=cuerpo,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[settings.ADMIN_EMAIL],
        fail_silently=True,
    )


def enviar_recordatorio_vencimiento(nutricionista, dias_restantes):
    """Mail al nutricionista avisándole que su suscripción vence pronto —
    para que no se entere recién cuando ya no puede entrar."""
    ctx = {'nutricionista': nutricionista, 'dias_restantes': dias_restantes, 'site_url': settings.SITE_URL}
    html = render_to_string('emails/recordatorio_vencimiento.html', ctx)
    send_mail(
        subject=f'Tu suscripción vence en {dias_restantes} día{"s" if dias_restantes != 1 else ""}',
        message=(
            f'Hola {nutricionista.user.first_name}, tu suscripción a NutricionClick vence el '
            f'{nutricionista.proxima_revision_pago.strftime("%d/%m/%Y")}. Renová desde tu dashboard.'
        ),
        from_email=settings.EMAIL_FROM,
        recipient_list=[nutricionista.user.email],
        html_message=html,
        fail_silently=True,
    )


def enviar_aviso_cuenta_suspendida(nutricionista):
    """Mail al nutricionista el día que su cuenta queda suspendida por falta
    de pago — así entiende por qué no puede entrar en vez de asumir que la
    web está rota."""
    ctx = {'nutricionista': nutricionista, 'site_url': settings.SITE_URL}
    html = render_to_string('emails/cuenta_suspendida.html', ctx)
    send_mail(
        subject='Tu cuenta en NutricionClick fue suspendida por falta de pago',
        message=(
            f'Hola {nutricionista.user.first_name}, tu suscripción venció y no detectamos el pago, '
            f'así que tu cuenta quedó suspendida. Renová desde tu dashboard para reactivarla.'
        ),
        from_email=settings.EMAIL_FROM,
        recipient_list=[nutricionista.user.email],
        html_message=html,
        fail_silently=True,
    )


def enviar_bienvenida(nutricionista):
    """Mail al nutricionista cuando su cuenta es aprobada."""
    html = render_to_string('emails/bienvenida.html', {'nutricionista': nutricionista})
    send_mail(
        subject='¡Tu cuenta en NutricionClick fue aprobada!',
        message=f'Hola {nutricionista.user.first_name}, tu cuenta fue aprobada. Ya podés ingresar a NutricionClick.',
        from_email=settings.EMAIL_FROM,
        recipient_list=[nutricionista.user.email],
        html_message=html,
        fail_silently=True,
    )


def enviar_confirmacion_turno(turno):
    """Mail al nutricionista cuando crea o modifica un turno."""
    html = render_to_string('emails/turno_confirmado.html', {'turno': turno})
    send_mail(
        subject=f'Turno confirmado — {_local(turno.fecha_hora_inicio).strftime("%d/%m/%Y %H:%M")}',
        message=f'Turno agendado para {_local(turno.fecha_hora_inicio).strftime("%d/%m/%Y a las %H:%M")}.',
        from_email=settings.EMAIL_FROM,
        recipient_list=[turno.nutricionista.user.email],
        html_message=html,
        fail_silently=True,
    )


def enviar_reserva_online(turno, turnero):
    """Mail al paciente y al nutricionista cuando se reserva online."""
    link_turno = settings.SITE_URL.rstrip('/') + f'/turnero/turno/{turno.token}/'
    ctx = {'turno': turno, 'turnero': turnero, 'nutri': turno.nutricionista,
           'link_turno': link_turno}
    # Al paciente
    if turno.email_destino:
        html = render_to_string('emails/reserva_paciente.html', ctx)
        send_mail(
            subject=f'Tu turno del {_local(turno.fecha_hora_inicio).strftime("%d/%m/%Y a las %H:%M")} hs',
            message=f'Reservaste un turno para el {_local(turno.fecha_hora_inicio).strftime("%d/%m/%Y a las %H:%M")} hs.',
            from_email=settings.EMAIL_FROM,
            recipient_list=[turno.email_destino],
            html_message=html,
            fail_silently=True,
        )
    # Al nutricionista
    html = render_to_string('emails/reserva_nutricionista.html', ctx)
    send_mail(
        subject=f'Nueva reserva online — {turno.nombre_display} — {_local(turno.fecha_hora_inicio).strftime("%d/%m %H:%M")} hs',
        message=f'{turno.nombre_display} reservo un turno para el {_local(turno.fecha_hora_inicio).strftime("%d/%m/%Y a las %H:%M")} hs.',
        from_email=settings.EMAIL_FROM,
        recipient_list=[turno.nutricionista.user.email],
        html_message=html,
        fail_silently=True,
    )


def enviar_recordatorio_sena(turno, turnero, link_pago):
    """Recordatorio (por defecto 24hs antes) con el link de pago de la seña."""
    if not turno.email_destino:
        return
    ctx = {'turno': turno, 'turnero': turnero, 'nutri': turno.nutricionista, 'link_pago': link_pago}
    html = render_to_string('emails/recordatorio_sena.html', ctx)
    send_mail(
        subject=f'Confirma tu turno — seña del {turnero.porcentaje_sena}%',
        message=(
            f'Tu turno es el {_local(turno.fecha_hora_inicio).strftime("%d/%m/%Y a las %H:%M")} hs. '
            f'Para confirmarlo, abona la seña de ${turno.sena_monto} aca: {link_pago}'
        ),
        from_email=settings.EMAIL_FROM,
        recipient_list=[turno.email_destino],
        html_message=html,
        fail_silently=True,
    )


def enviar_sena_confirmada(turno, turnero):
    """Aviso a ambas partes cuando la seña fue acreditada."""
    ctx = {'turno': turno, 'turnero': turnero, 'nutri': turno.nutricionista}
    if turno.email_destino:
        html = render_to_string('emails/sena_confirmada.html', ctx)
        send_mail(
            subject=f'¡Turno confirmado! — {_local(turno.fecha_hora_inicio).strftime("%d/%m/%Y %H:%M")} hs',
            message=f'Recibimos tu seña. Tu turno del {_local(turno.fecha_hora_inicio).strftime("%d/%m/%Y a las %H:%M")} hs quedo confirmado.',
            from_email=settings.EMAIL_FROM,
            recipient_list=[turno.email_destino],
            html_message=html,
            fail_silently=True,
        )
    send_mail(
        subject=f'Seña recibida — {turno.nombre_display} — {_local(turno.fecha_hora_inicio).strftime("%d/%m %H:%M")} hs',
        message=f'{turno.nombre_display} abono la seña de ${turno.sena_monto}. El turno quedo confirmado.',
        from_email=settings.EMAIL_FROM,
        recipient_list=[turno.nutricionista.user.email],
        fail_silently=True,
    )


def enviar_turno_liberado(turno, turnero):
    """Aviso al paciente de que su turno se libero por seña impaga."""
    if not turno.email_destino:
        return
    link_reservar = settings.SITE_URL.rstrip('/') + f'/reservar/{turno.nutricionista.slug}/'
    ctx = {'turno': turno, 'turnero': turnero, 'nutri': turno.nutricionista,
           'link_reservar': link_reservar}
    html = render_to_string('emails/turno_liberado.html', ctx)
    send_mail(
        subject='Tu turno fue liberado por falta de seña',
        message=(
            f'Como no recibimos la seña, tu turno del '
            f'{_local(turno.fecha_hora_inicio).strftime("%d/%m/%Y a las %H:%M")} hs fue liberado. '
            f'Podes reservar uno nuevo cuando quieras.'
        ),
        from_email=settings.EMAIL_FROM,
        recipient_list=[turno.email_destino],
        html_message=html,
        fail_silently=True,
    )


def enviar_planes_info(contacto):
    """Mail automático al interesado con el detalle de ambos planes, precios y CTA.

    El botón de cada plan lleva directo al registro — ahí es donde se elige
    el plan real y se cobra automáticamente (con o sin código de descuento),
    no hay links de pago fijos por país.
    """
    planes = {
        'herramientas': 'Plan Completo — Publicidad + Herramientas',
        'publicidad': 'Plan Básico — Solo publicidad',
        'sin_definir': None,
    }
    pais = contacto.pais
    html = render_to_string('emails/planes_info.html', {
        'nombre': contacto.nombre,
        'pais': pais,
        'plan_label': planes.get(contacto.plan_interes),
        'whatsapp_admin': settings.ADMIN_WHATSAPP,
        # Gmail reescribe el "De:" para que coincida con la cuenta autenticada
        # (EMAIL_HOST_USER) aunque EMAIL_FROM diga otra cosa — usamos esa acá
        # para que el tip de "agregá X a tus contactos" sea el mail real.
        # EMAIL_HOST_USER solo existe cuando el backend SMTP está activo
        # (con EMAIL_HOST_PASSWORD configurado) — getattr por si no lo está.
        'email_remitente': getattr(settings, 'EMAIL_HOST_USER', None) or settings.EMAIL_FROM,
        'link_registro': settings.SITE_URL.rstrip('/') + '/registro/',
    })
    send_mail(
        subject='Los planes de NutricionClick para vos',
        message=(
            f'Hola {contacto.nombre}, gracias por tu interés en NutricionClick. '
            f'Te contactamos pronto — mientras tanto, respondé este mail si tenés preguntas sobre los planes.'
        ),
        from_email=settings.EMAIL_FROM,
        recipient_list=[contacto.email],
        html_message=html,
        fail_silently=True,
    )


def enviar_resumen_diario(nutricionista, turnos):
    """Resumen de turnos del día al nutricionista."""
    if not turnos:
        return
    html = render_to_string('emails/resumen_diario.html', {
        'nutricionista': nutricionista,
        'turnos': turnos,
    })
    send_mail(
        subject=f'Tus turnos de hoy — {_local(turnos[0].fecha_hora_inicio).strftime("%d/%m/%Y")}',
        message=f'Tenés {len(turnos)} turno(s) hoy.',
        from_email=settings.EMAIL_FROM,
        recipient_list=[nutricionista.user.email],
        html_message=html,
        fail_silently=True,
    )


