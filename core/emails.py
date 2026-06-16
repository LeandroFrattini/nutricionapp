from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string


def enviar_bienvenida(nutricionista):
    """Mail al nutricionista cuando su cuenta es aprobada."""
    html = render_to_string('emails/bienvenida.html', {'nutricionista': nutricionista})
    send_mail(
        subject='¡Tu cuenta en NutriLink fue aprobada!',
        message=f'Hola {nutricionista.user.first_name}, tu cuenta fue aprobada. Ya podés ingresar a NutriLink.',
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
