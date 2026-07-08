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
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import reverse
from django.utils import timezone

from core import emails
from core.models import ConfiguracionTurnero, Turno


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
            for turno in pendientes:
                link_pago = settings.SITE_URL.rstrip('/') + reverse(
                    'turnero_pagar', kwargs={'token': turno.token}
                )
                turno.estado = 'pendiente_sena'
                turno.recordatorio_enviado_en = ahora
                turno.save(update_fields=['estado', 'recordatorio_enviado_en'])
                emails.enviar_recordatorio_sena(turno, turnero, link_pago)
                recordatorios += 1
                self.stdout.write(f'  → Recordatorio: {turno.nombre_display} — {turno.fecha_hora_inicio:%d/%m %H:%M}')

            # ── 2. Liberar turnos con seña impaga ─────────────────────────
            limite_pago = ahora + timedelta(hours=turnero.horas_limite_pago)
            vencidos = Turno.objects.filter(
                nutricionista=turnero.nutricionista,
                origen='online',
                estado='pendiente_sena',
                sena_pagada=False,
                fecha_hora_inicio__lte=limite_pago,
            )
            for turno in vencidos:
                turno.estado = 'vencido'
                turno.save(update_fields=['estado'])
                emails.enviar_turno_liberado(turno, turnero)
                liberados += 1
                self.stdout.write(f'  → Liberado: {turno.nombre_display} — {turno.fecha_hora_inicio:%d/%m %H:%M}')

        self.stdout.write(self.style.SUCCESS(
            f'Turnero procesado: {recordatorios} recordatorio(s), {liberados} turno(s) liberado(s).'
        ))
