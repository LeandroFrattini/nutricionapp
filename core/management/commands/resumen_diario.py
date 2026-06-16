"""
Comando para enviar el resumen diario de turnos.
Ejecutar manualmente: python manage.py resumen_diario
Programar en Windows Task Scheduler o cron para correr a las 7am.
"""
from datetime import date
from django.core.management.base import BaseCommand
from core.models import Nutricionista, Turno
from core.emails import enviar_resumen_diario


class Command(BaseCommand):
    help = 'Envía el resumen diario de turnos a cada nutricionista'

    def handle(self, *args, **options):
        hoy = date.today()
        nutricionistas = Nutricionista.objects.filter(aprobado=True, user__is_active=True)
        enviados = 0

        for nutri in nutricionistas:
            turnos = list(Turno.objects.filter(
                nutricionista=nutri,
                fecha_hora_inicio__date=hoy,
                estado__in=['pendiente', 'confirmado']
            ).order_by('fecha_hora_inicio'))

            if turnos:
                enviar_resumen_diario(nutri, turnos)
                enviados += 1
                self.stdout.write(f'  → {nutri} — {len(turnos)} turno(s)')

        self.stdout.write(self.style.SUCCESS(
            f'Resumen diario enviado a {enviados} nutricionista(s).'
        ))
