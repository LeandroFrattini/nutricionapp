"""
Manda un mail de PRUEBA real (no simulado, no mockeado) para confirmar que
el envio de mails esta funcionando de verdad en el entorno donde se corre
este comando -- usa el mismo EMAIL_BACKEND que usa toda la app.

Sirve para responder una sola pregunta con certeza: "¿los mails realmente
estan saliendo desde ACA (este servidor, estas credenciales)?" -- algo que
ningun test automatizado puede contestar, porque los tests siempre corren
con el backend de memoria de Django (no hablan con Gmail de verdad).

Ejecutar en local:
  python manage.py probar_email tu@email.com

Ejecutar en produccion (Render): abrir la Shell del servicio web desde el
dashboard de Render y correr el mismo comando ahi -- eso prueba las
credenciales REALES de produccion, no las de tu maquina.
"""
from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Manda un mail de prueba real para confirmar que el envio de mails esta funcionando'

    def add_arguments(self, parser):
        parser.add_argument('destinatario', help='Email adonde mandar la prueba')

    def handle(self, *args, **options):
        destinatario = options['destinatario']
        backend = settings.EMAIL_BACKEND

        self.stdout.write(f'EMAIL_BACKEND activo: {backend}')
        self.stdout.write(f'EMAIL_HOST: {getattr(settings, "EMAIL_HOST", "(no aplica)")}')
        self.stdout.write(f'EMAIL_HOST_USER: {getattr(settings, "EMAIL_HOST_USER", "(no aplica)")}')

        if 'console' in backend:
            self.stdout.write(self.style.ERROR(
                '\nATENCION: el backend activo es "consola". Esto pasa cuando '
                'EMAIL_HOST_PASSWORD no esta cargado en este entorno -- significa que '
                'NINGUN mail se manda de verdad ahora mismo, solo se imprime aca abajo. '
                'Si esto da "consola" corriendo este comando en la Shell de Render '
                '(produccion), ESA es la causa raiz de que los mails "no lleguen a '
                'ningun lado" -- hay que cargar EMAIL_HOST_PASSWORD en las variables '
                'de entorno de Render.\n'
            ))

        try:
            enviados = send_mail(
                subject='[NutricionClick] Mail de prueba',
                message=(
                    f'Si estas leyendo esto en tu bandeja de entrada (no en una consola), '
                    f'el envio de mails esta funcionando bien.\n\n'
                    f'Backend usado: {backend}'
                ),
                from_email=settings.EMAIL_FROM,
                recipient_list=[destinatario],
                fail_silently=False,
            )
        except Exception as exc:
            raise CommandError(f'El envio fallo con un error (esto SI es un problema real de configuracion): {exc}')

        if not enviados:
            self.stdout.write(self.style.ERROR('send_mail no informo ningun envio exitoso.'))
            return

        if 'console' in backend:
            self.stdout.write(self.style.WARNING(
                f'"Enviado" sin error, pero como el backend es "consola", en los hechos '
                f'NO llego a la bandeja de {destinatario} -- solo se imprimio arriba.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Mail despachado por SMTP a {destinatario} sin errores. '
                f'Revisa esa bandeja (y la carpeta de spam) para confirmar que llego.'
            ))
