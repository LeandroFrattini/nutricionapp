"""
Procesa el turnero online:
  1. Envia el recordatorio con link de pago de la seña a los turnos que
     estan a menos de X horas (configurable por nutricionista, default 24).
  2. Libera (marca 'vencido') los turnos cuya seña no se pago al llegar
     la hora limite, dejando el horario disponible de nuevo.

Ejecutar manualmente: python manage.py procesar_turnero
Programar cada 30-60 min en cron / Windows Task Scheduler:
  */30 * * * * cd /ruta/proyecto && python manage.py procesar_turnero
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import reverse
from django.utils import timezone

from core import emails
from core.models import ConfiguracionTurnero, Turno

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Envia recordatorios de seña y libera turnos con seña impaga'

    def handle(self, *args, **options):
        ahora = timezone.now()
        recordatorios = 0
        liberados = 0

        turneros = ConfiguracionTurnero.objects.filter(
            activo=True, requiere_sena=True
        ).select_related('nutricionista')

        for turnero in turneros:
            # ── 1. Recordatorios con link de pago ─────────────────────────
            limite_recordatorio = ahora + timedelta(hours=turnero.horas_recordatorio)
            pendientes = Turno.objects.filter(
                nutricionista=turnero.nutricionista,
                origen='online',
                estado='pendiente',
                sena_monto__isnull=False,
                recordatorio_enviado_en__isnull=True,
                fecha_hora_inicio__gt=ahora,
                fecha_hora_inicio__lte=limite_recordatorio,
            )
            # Turnos a los que se les acaba de avisar en ESTA corrida — no
            # pueden liberarse en el paso 2 de más abajo por más que ya
            # estén dentro de la ventana de horas_limite_pago (pasa con
            # turnos reservados con poca anticipación: si el recordatorio se
            # manda recién ahora, el paciente tiene que tener al menos hasta
            # la corrida siguiente para pagar, no cero segundos).
            recien_avisados_ids = set()
            for turno in pendientes:
                try:
                    link_pago = settings.SITE_URL.rstrip('/') + reverse(
                        'turnero_pagar', kwargs={'token': turno.token}
                    )
                    enviado = emails.enviar_recordatorio_sena(turno, turnero, link_pago)
                    if not enviado:
                        # CRÍTICO: si el mail no se pudo mandar, el turno NO
                        # puede avanzar a "pendiente_sena" — si lo hiciera,
                        # quedaría camino a liberarse solo (paso 2, más
                        # abajo) sin que el paciente se haya enterado nunca
                        # de que tenía que pagar la seña. Se deja tal cual
                        # para que se reintente en la próxima corrida, y se
                        # avisa por mail para que alguien lo resuelva a mano
                        # si el problema persiste.
                        emails.enviar_alerta_recordatorio_sena_fallido(turno)
                        self.stdout.write(self.style.WARNING(
                            f'  [!] No se pudo mandar el recordatorio a {turno.nombre_display} '
                            f'({turno.fecha_hora_inicio:%d/%m %H:%M}) - se reintenta en la proxima corrida'
                        ))
                        continue
                    turno.estado = 'pendiente_sena'
                    turno.recordatorio_enviado_en = ahora
                    turno.save(update_fields=['estado', 'recordatorio_enviado_en'])
                    recien_avisados_ids.add(turno.pk)
                    recordatorios += 1
                    # El write va DESPUES de guardar el estado y mandar el
                    # mail — si el print explota (por ejemplo, la consola de
                    # Windows no soporta algun caracter), no se puede perder
                    # el efecto real ya hecho.
                    self.stdout.write(f'  -> Recordatorio: {turno.nombre_display} - {turno.fecha_hora_inicio:%d/%m %H:%M}')
                except Exception:
                    logger.exception('procesar_turnero: fallo procesando el recordatorio del turno %s', turno.pk)

            # ── 2. Liberar turnos con seña impaga ─────────────────────────
            limite_pago = ahora + timedelta(hours=turnero.horas_limite_pago)
            vencidos = Turno.objects.filter(
                nutricionista=turnero.nutricionista,
                origen='online',
                estado='pendiente_sena',
                sena_pagada=False,
                fecha_hora_inicio__lte=limite_pago,
            ).exclude(pk__in=recien_avisados_ids)
            for turno in vencidos:
                try:
                    turno.estado = 'vencido'
                    turno.save(update_fields=['estado'])
                    emails.enviar_turno_liberado(turno, turnero)
                    liberados += 1
                    self.stdout.write(f'  -> Liberado: {turno.nombre_display} - {turno.fecha_hora_inicio:%d/%m %H:%M}')
                except Exception:
                    logger.exception('procesar_turnero: fallo liberando/notificando el turno %s', turno.pk)

        self.stdout.write(self.style.SUCCESS(
            f'Turnero procesado: {recordatorios} recordatorio(s), {liberados} turno(s) liberado(s).'
        ))
