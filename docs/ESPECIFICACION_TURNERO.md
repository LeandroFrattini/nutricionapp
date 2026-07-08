# Especificación — Turnero online con seña por Mercado Pago

**Proyecto:** NutricionClick (Nutri Link) · **Fecha:** julio 2026 · **Estado:** implementado

## Objetivo

Reducir los turnos perdidos y cancelados sin anticipación. Cada nutricionista dispone de un turnero online propio: define sus franjas horarias, comparte un link público y los pacientes reservan solos. Un día antes del turno (configurable), el paciente recibe un recordatorio automático con un link para abonar el 50% de la consulta (configurable) por Mercado Pago. Si no paga a tiempo, el turno se libera automáticamente.

## Flujo principal

1. **Reserva.** El paciente abre `/reservar/<slug>/`, elige día y horario entre los slots libres, deja nombre, apellido, email y teléfono. El turno se crea en estado `pendiente` con `origen='online'` y un token UUID que le permite gestionarlo sin login. Si el email coincide con un paciente existente del nutricionista, se vincula automáticamente. Ambas partes reciben email de confirmación de reserva.
2. **Recordatorio con seña.** El comando `procesar_turnero` (programado cada 30-60 min) detecta los turnos a menos de `horas_recordatorio` (default 24 hs), los pasa a `pendiente_sena` y envía al paciente el mail con el botón de pago. Si el paciente reserva con menos de 24 hs de anticipación, el pedido de seña se envía inmediatamente al reservar.
3. **Pago.** El link `/turnero/turno/<token>/pagar/` genera una preferencia de Checkout Pro en la cuenta de Mercado Pago del nutricionista y redirige al checkout. Al volver (o vía webhook), se verifica el pago contra la API: si está aprobado, el turno pasa a `confirmado`, se marca `sena_pagada` y ambas partes reciben aviso.
4. **Liberación.** Si al llegar `horas_limite_pago` (default 6 hs antes) la seña no se pagó, el mismo comando marca el turno `vencido`, avisa al paciente y el slot vuelve a estar disponible.
5. **Cancelación.** El paciente puede cancelar desde su página de turno (`/turnero/turno/<token>/`).

### Estados del turno

`pendiente` → `pendiente_sena` → `confirmado` → `realizado`
Con salidas: `cancelado` (paciente o nutricionista), `vencido` (seña impaga), `no_asistio`.

## Mercado Pago — modelo marketplace (OAuth)

- NutricionClick registra **una sola aplicación** en el panel de desarrolladores de MP (`MP_APP_ID` / `MP_CLIENT_SECRET` en `.env`).
- Cada nutricionista vincula su propia cuenta desde el dashboard con el botón "Vincular mi Mercado Pago" → OAuth en el sitio de MP → los tokens quedan guardados en `ConfiguracionTurnero`. La plataforma nunca ve credenciales.
- Las señas se cobran con el `access_token` del nutricionista: **el dinero va directo a su cuenta**.
- `MP_MARKETPLACE_FEE` permite definir una comisión fija por transacción para la plataforma (0 por defecto).
- Los tokens se refrescan automáticamente con el `refresh_token` cuando están por vencer.

## Modelo de datos

- **`ConfiguracionTurnero`** (OneToOne con `Nutricionista`): `activo`, `duracion_turno_minutos`, `anticipacion_maxima_dias`, `anticipacion_minima_horas`, `requiere_sena`, `precio_consulta`, `porcentaje_sena`, `horas_recordatorio`, `horas_limite_pago`, tokens de MP. Métodos clave: `monto_sena`, `listo_para_publicar`, `generar_slots(fecha)` (franjas − turnos ocupados − bloqueos − anticipación mínima).
- **`FranjaHoraria`**: día de semana + hora inicio/fin. Varias por día permitidas, sin superposición.
- **`BloqueoFecha`**: rango de fechas bloqueado (vacaciones, feriados) con motivo.
- **`Turno`** (extendido): `origen`, `token` (UUID único), datos de contacto de la reserva online, `sena_monto`, `sena_pagada(_en)`, `mp_preference_id`, `mp_payment_id`, `recordatorio_enviado_en`, y estados nuevos `pendiente_sena` / `vencido` / `no_asistio`.

## Archivos

| Archivo | Contenido |
|---|---|
| `core/models.py` | Modelos nuevos + extensión de `Turno` (además se reparó una corrupción del archivo por sync de OneDrive) |
| `core/migrations/0010_turnero_online.py` | Migración (incluye backfill de tokens para turnos existentes) |
| `core/views_turnero.py` | Configuración del dashboard, reserva pública, OAuth MP, pago, webhook, cancelación |
| `core/mercadopago.py` | Cliente de la API de MP: OAuth, refresh, preferencias, verificación de pagos |
| `core/emails.py` | 4 emails nuevos: reserva (paciente y nutri), recordatorio de seña, seña confirmada, turno liberado |
| `core/management/commands/procesar_turnero.py` | Recordatorios + liberación de turnos impagos |
| `core/admin.py` | Admin de `ConfiguracionTurnero` con franjas y bloqueos inline |
| `templates/turnero/configuracion.html` | Pantalla didáctica en 4 pasos con botón grande de copiar/compartir link |
| `templates/turnero/reservar.html` | Página pública de reserva (día → horario → datos) |
| `templates/turnero/reservado.html` | Estado del turno para el paciente (pagar / cancelar) |
| `templates/turnero/cancelar.html`, `no_disponible.html` | Auxiliares |
| `templates/emails/*.html` | 5 templates de email nuevos |
| `templates/base_dashboard.html` | Ítem "Turnero online" en el menú |
| `templates/perfil/publico.html` | Botón "RESERVAR TURNO ONLINE" en el perfil público |
| `nutricion/settings.py`, `.env.example` | `SITE_URL`, `MP_APP_ID`, `MP_CLIENT_SECRET`, `MP_MARKETPLACE_FEE` |
| `requirements.txt` | Se agregó `requests` |

## Puesta en marcha

1. `pip install requests` (o `pip install -r requirements.txt`).
2. `python manage.py migrate`.
3. Crear la aplicación en el [panel de desarrolladores de Mercado Pago](https://www.mercadopago.com.ar/developers/panel/app) (Checkout Pro, marketplace), configurar la Redirect URI `https://TU-DOMINIO/turnero/mp/callback/` y completar `MP_APP_ID`, `MP_CLIENT_SECRET` y `SITE_URL` en el `.env`.
4. Programar `python manage.py procesar_turnero` cada 30-60 min (Task Scheduler en Windows / cron en el servidor), igual que `resumen_diario`.

## Decisiones y pendientes

- **La plataforma no toca el dinero**: solo intermedia el link de pago (simplifica lo legal/impositivo). La comisión opcional queda lista vía `marketplace_fee`.
- **Devoluciones**: si el paciente cancela habiendo pagado la seña, la devolución queda a criterio del nutricionista (se hace desde su propio panel de MP). Automatizarlo es una mejora futura.
- **Mejoras futuras**: recordatorio también por WhatsApp, reprogramación con crédito de seña, seña obligatoria al reservar (en vez de 24 hs antes) para pacientes nuevos, panel de métricas de ausentismo.
