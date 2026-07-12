"""
Comando diario de vencimientos de suscripción:
  - Avisa por mail al nutricionista 3 días antes de que venza.
  - Avisa por mail al nutricionista el día que su cuenta queda suspendida
    (5 días después del vencimiento).
  - Avisa por mail al admin la lista completa de suspendidos hoy, para
    seguimiento manual.
Ejecutar manualmente: python manage.py revisar_suscripciones
Programar en Windows Task Scheduler o cron para correr una vez por día.
"""
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from core.models import Nutricionista
from core.emails import enviar_alerta_suspension, enviar_recordatorio_vencimiento, enviar_aviso_cuenta_suspendida

DIAS_AVISO_PREVIO = 3
DIAS_GRACIA = 5  # tiene que coincidir con Nutricionista.suspendido_por_pago()


class Command(BaseCommand):
    help = 'Avisa por mail vencimientos próximos, suspensiones nuevas, y resume al admin quién está suspendido'

    def handle(self, *args, **options):
        hoy = date.today()
        base = Nutricionista.objects.filter(aprobado=True, exento_de_pago=False).select_related('user')

        proximos_a_vencer = base.filter(proxima_revision_pago=hoy + timedelta(days=DIAS_AVISO_PREVIO))
        for n in proximos_a_vencer:
            enviar_recordatorio_vencimiento(n, DIAS_AVISO_PREVIO)
            self.stdout.write(f'  recordatorio -> {n.user.get_full_name()}')

        recien_suspendidos = base.filter(proxima_revision_pago=hoy - timedelta(days=DIAS_GRACIA + 1))
        for n in recien_suspendidos:
            enviar_aviso_cuenta_suspendida(n)
            self.stdout.write(f'  suspendido (aviso nuevo) -> {n.user.get_full_name()}')

        candidatos = base.exclude(proxima_revision_pago__isnull=True).order_by('proxima_revision_pago')
        suspendidos = [n for n in candidatos if n.suspendido_por_pago()]
        if suspendidos:
            enviar_alerta_suspension(suspendidos)
            for n in suspendidos:
                self.stdout.write(f'  -> {n.user.get_full_name()} — vencido hace {abs(n.dias_para_vencimiento())} día(s)')

        self.stdout.write(self.style.SUCCESS(
            f'{proximos_a_vencer.count()} recordatorio(s), {recien_suspendidos.count()} suspensión(es) nueva(s), '
            f'{len(suspendidos)} suspendido(s) en total.'
        ))
