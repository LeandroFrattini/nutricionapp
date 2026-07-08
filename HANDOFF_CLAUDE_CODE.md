# Handoff para Claude Code — NutricionClick (Nutri Link)

Proyecto Django 6 + SQLite + Tailwind CDN + htmx. App única: `core`. DB en `~/.nutrilink/db.sqlite3` (fuera del repo por OneDrive). Idioma: español (Argentina), TZ America/Argentina/Buenos_Aires.

## Qué se implementó recientemente (sesiones de Cowork)

### 1. Turnero online con seña por Mercado Pago
Flujo: el paciente reserva desde un link público (`/reservar/<slug>/`) → 24 hs antes (configurable) recibe email con link para pagar la seña (50% configurable) vía Mercado Pago → si paga, turno `confirmado`; si no paga, a las 6 hs antes (configurable) el turno pasa a `vencido` y el slot se libera.

- **Modelos** (`core/models.py`): `ConfiguracionTurnero` (OneToOne con Nutricionista; franjas, precios, % seña, tokens MP OAuth, método `generar_slots(fecha)`), `FranjaHoraria`, `BloqueoFecha`. `Turno` extendido: estados nuevos (`pendiente_sena`, `vencido`, `no_asistio`), `origen`, `token` UUID único, datos de contacto de reserva online, campos de seña/pago MP.
- **Migración**: `core/migrations/0010_turnero_online.py`. Incluye patrón de 3 pasos para el token único + `poblar_tokens` que recorre TODOS los turnos (SQLite deja el mismo UUID repetido en el AddField). Ya se corrió `migrate` con éxito en la máquina del usuario.
- **Vistas**: `core/views_turnero.py` (config del dashboard, franjas/bloqueos, OAuth MP conectar/callback/desconectar, reserva pública, pagar, retorno de pago, webhook, cancelación pública). URLs en `core/urls.py`.
- **Mercado Pago**: `core/mercadopago.py` — modelo marketplace vía OAuth: cada nutricionista vincula SU cuenta; la plataforma solo guarda tokens; preferencias CheckoutPro con `external_reference=turno.token`; `MP_MARKETPLACE_FEE` opcional.
- **Emails**: `core/emails.py` + `templates/emails/` (reserva_paciente, reserva_nutricionista, recordatorio_sena, sena_confirmada, turno_liberado).
- **Comando**: `core/management/commands/procesar_turnero.py` — enviar recordatorios de seña + liberar impagos. Debe programarse cada 30-60 min (Task Scheduler / cron). Aún NO está programado.
- **Templates**: `templates/turnero/` (configuracion con wizard de 4 pasos y botón grande copiar/compartir link, reservar, reservado, cancelar, no_disponible). Link "Turnero online" en sidebar de `base_dashboard.html`; botón "RESERVAR TURNO ONLINE" en `perfil/publico.html` y en el modal del home.
- **Settings/.env**: `SITE_URL`, `MP_APP_ID`, `MP_CLIENT_SECRET`, `MP_MARKETPLACE_FEE` (ver `.env.example`). `requests` agregado a `requirements.txt`.
- **Spec completa**: `docs/ESPECIFICACION_TURNERO.md`.

### 2. Rebrand visual (verde → violeta/teal)
Paleta nueva: primario violeta `#7A5AB4` (hover `#5E4694`, profundo `#2E2447`), acento teal `#168486`. Aplicada en todos los templates, logos SVG (`static/img/`) y sidebar del dashboard (`#251C3D`). `base.html` define colores `brand-*` y `accent-*` en la config de Tailwind + clases `.btn-primary`, `.btn-secondary`, `.text-gradient`. `home.html` fue rediseñado (hero con gradiente, trust markers, sección "cómo funciona", stats en violeta profundo, CTA violeta→teal). Los verdes solo quedan donde son semánticos (mensajes success, botones de WhatsApp `#25D366`).

## ⚠️ Tareas para vos (Claude Code) — verificar y terminar

1. **Chequeo de integridad por OneDrive (IMPORTANTE).** El proyecto vive en OneDrive y hubo problemas de sincronización que dejaron archivos truncados a mitad de línea en el pasado (ya reparados: `core/models.py`). Correr:
   - `python -m py_compile core/models.py core/views.py core/views_turnero.py core/emails.py core/mercadopago.py core/urls.py core/admin.py`
   - `python manage.py check`
   - Verificar que ningún template termine cortado (todos los `{% block %}` cerrados): renderizar las páginas clave (ver punto 3).
2. **Migraciones**: `python manage.py migrate` (0010 ya aplicada; confirmar que `showmigrations` está al día y que `makemigrations --check --dry-run` no detecta cambios pendientes).
3. **Smoke test de renderizado** (con `python manage.py runserver` o test client): `/`, `/nutricionistas/`, `/login/`, `/quiero-ser-parte/`, `/nutricionistas/<slug>/`, `/reservar/<slug>/`, y logueado: `/dashboard/`, `/dashboard/turnero/`, `/dashboard/agenda/`, `/dashboard/pacientes/`. Nada debe dar 500. El flujo de reserva ya fue testeado end-to-end (reserva, doble-reserva bloqueada, recordatorio, liberación de impagos) en un entorno espejo.
4. **Revisar restos de la paleta vieja**: buscar `#1B4332`, `#14532d`, `#2d6a4f`, `#16a34a`, `forest`, `bark` en templates y static — no debería quedar ninguno. Si quedan chips `bg-green-*`/`text-green-*` que NO sean mensajes de éxito ni WhatsApp, pasarlos a `purple`/`teal`.
5. **Consistencia visual**: el dashboard (`base_dashboard.html`) usa sidebar `#251C3D` con links `#b9a9dd`; revisar contraste y que los templates internos (agenda, pacientes, mediciones) se vean coherentes con el violeta. Ajustar lo que desentone.
6. **Pendientes de configuración del usuario** (no bloqueantes, solo recordar): crear app en el panel de desarrolladores de Mercado Pago (CheckoutPro, marketplace, redirect URI `https://DOMINIO/turnero/mp/callback/`), completar `.env`, y programar `python manage.py procesar_turnero` cada 30-60 min en el Programador de tareas de Windows.
7. **Git**: hay muchos cambios sin commitear (incluye la reparación de `core/models.py` que estaba corrupto). Hacer commits ordenados, p. ej.: `fix: reparar models.py truncado por sync OneDrive`, `feat: turnero online con seña Mercado Pago`, `style: rebrand violeta/teal + home profesional`.

## Convenciones del proyecto
- Español rioplatense en UI y mensajes ("vos", "reservá").
- Sin dependencias de frontend: Tailwind por CDN, htmx, JS vanilla inline.
- Los nutricionistas usan solo el dashboard (no son staff); el admin de Django es solo para el dueño.
- Emails con `fail_silently=True` y backend consola si no hay SMTP configurado.
