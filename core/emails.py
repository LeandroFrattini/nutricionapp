from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string


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
        subject=f'Turno confirmado — {turno.fecha_hora_inicio.strftime("%d/%m/%Y %H:%M")}',
        message=f'Turno agendado para {turno.fecha_hora_inicio.strftime("%d/%m/%Y a las %H:%M")}.',
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
            subject=f'Tu turno del {turno.fecha_hora_inicio.strftime("%d/%m/%Y a las %H:%M")} hs',
            message=f'Reservaste un turno para el {turno.fecha_hora_inicio.strftime("%d/%m/%Y a las %H:%M")} hs.',
            from_email=settings.EMAIL_FROM,
            recipient_list=[turno.email_destino],
            html_message=html,
            fail_silently=True,
        )
    # Al nutricionista
    html = render_to_string('emails/reserva_nutricionista.html', ctx)
    send_mail(
        subject=f'Nueva reserva online — {turno.nombre_display} — {turno.fecha_hora_inicio.strftime("%d/%m %H:%M")} hs',
        message=f'{turno.nombre_display} reservo un turno para el {turno.fecha_hora_inicio.strftime("%d/%m/%Y a las %H:%M")} hs.',
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
            f'Tu turno es el {turno.fecha_hora_inicio.strftime("%d/%m/%Y a las %H:%M")} hs. '
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
            subject=f'¡Turno confirmado! — {turno.fecha_hora_inicio.strftime("%d/%m/%Y %H:%M")} hs',
            message=f'Recibimos tu seña. Tu turno del {turno.fecha_hora_inicio.strftime("%d/%m/%Y a las %H:%M")} hs quedo confirmado.',
            from_email=settings.EMAIL_FROM,
            recipient_list=[turno.email_destino],
            html_message=html,
            fail_silently=True,
        )
    send_mail(
        subject=f'Seña recibida — {turno.nombre_display} — {turno.fecha_hora_inicio.strftime("%d/%m %H:%M")} hs',
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
            f'{turno.fecha_hora_inicio.strftime("%d/%m/%Y a las %H:%M")} hs fue liberado. '
            f'Podes reservar uno nuevo cuando quieras.'
        ),
        from_email=settings.EMAIL_FROM,
        recipient_list=[turno.email_destino],
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
        subject=f'Tus turnos de hoy — {turnos[0].fecha_hora_inicio.strftime("%d/%m/%Y")}',
        message=f'Tenés {len(turnos)} turno(s) hoy.',
        from_email=settings.EMAIL_FROM,
        recipient_list=[nutricionista.user.email],
        html_message=html,
        fail_silently=True,
    )
