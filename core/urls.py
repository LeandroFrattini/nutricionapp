from django.urls import path
from . import views
from . import views_turnero
from . import views_portal
from . import views_panel
from . import views_pago

urlpatterns = [
    path('', views.home, name='home'),
    path('nutricionistas/', views.nutricionistas_lista, name='nutricionistas_lista'),
    path('nutricionistas/<slug:slug>/', views.perfil_publico, name='perfil_publico'),
    path('quiero-ser-parte/', views.quiero_ser_parte, name='quiero_ser_parte'),
    path('que-puedo-hacer/', views.que_puedo_hacer, name='que_puedo_hacer'),
    path('registro/', views.registro, name='registro'),
    path('registro/pagar/<int:pk>/', views_pago.registro_pagar, name='registro_pagar'),
    path('registro/pago/listo/', views_pago.registro_pago_listo, name='registro_pago_listo'),
    path('suscripcion/pago/<int:pago_pk>/retorno/', views_pago.pago_retorno, name='pago_retorno'),
    path('suscripcion/mp/webhook/', views_pago.mp_webhook_pago, name='mp_webhook_pago'),
    path('dashboard/renovar/', views_pago.renovar, name='renovar'),
    path('dashboard/perfil-suspendido/', views_pago.perfil_suspendido, name='perfil_suspendido'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/en-revision/', views.en_revision, name='en_revision'),
    path('dashboard/perfil/', views.perfil_editar, name='perfil_editar'),
    path('perfil/ciudades-por-provincia/', views.ciudades_por_provincia, name='ciudades_por_provincia'),
    # Pacientes
    path('dashboard/pacientes/', views.pacientes_lista, name='pacientes_lista'),
    path('dashboard/pacientes/nuevo/', views.paciente_nuevo, name='paciente_nuevo'),
    path('dashboard/pacientes/<int:pk>/', views.paciente_detalle, name='paciente_detalle'),
    path('dashboard/pacientes/<int:pk>/editar/', views.paciente_editar, name='paciente_editar'),
    path('dashboard/pacientes/<int:pk>/archivar/', views.paciente_archivar, name='paciente_archivar'),
    path('dashboard/pacientes/<int:pk>/reactivar/', views.paciente_reactivar, name='paciente_reactivar'),
    # Mediciones
    path('dashboard/pacientes/<int:pk>/medicion/nueva/', views.medicion_nueva, name='medicion_nueva'),
    path('dashboard/pacientes/<int:pk>/medicion/<int:mid>/editar/', views.medicion_editar, name='medicion_editar'),
    # Laboratorio
    path('dashboard/pacientes/<int:pk>/laboratorio/nuevo/', views.laboratorio_nuevo, name='laboratorio_nuevo'),
    path('dashboard/pacientes/<int:pk>/laboratorio/<int:lid>/editar/', views.laboratorio_editar, name='laboratorio_editar'),
    path('dashboard/pacientes/<int:pk>/laboratorio/<int:lid>/descargar/', views.laboratorio_descargar, name='laboratorio_descargar'),
    # Plan alimentario
    path('dashboard/pacientes/<int:pk>/plan/nuevo/', views.plan_nuevo, name='plan_nuevo'),
    path('dashboard/pacientes/<int:pk>/plan/<int:pid>/editar/', views.plan_editar, name='plan_editar'),
    path('dashboard/pacientes/<int:pk>/plan/<int:pid>/descargar/', views.plan_descargar, name='plan_descargar'),
    # Consultas
    path('dashboard/pacientes/<int:pk>/consulta/nueva/', views.consulta_nueva, name='consulta_nueva'),
    path('dashboard/pacientes/<int:pk>/consulta/<int:cid>/editar/', views.consulta_editar, name='consulta_editar'),
    # Archivos
    path('dashboard/pacientes/<int:pk>/archivo/nuevo/', views.archivo_nuevo, name='archivo_nuevo'),
    path('dashboard/pacientes/<int:pk>/archivo/<int:aid>/eliminar/', views.archivo_eliminar, name='archivo_eliminar'),
    path('archivo/<uuid:token>/', views.archivo_ver, name='archivo_ver'),
    # Agenda
    path('dashboard/agenda/', views.agenda, name='agenda'),
    path('dashboard/agenda/turno/nuevo/', views.turno_nuevo, name='turno_nuevo'),
    path('dashboard/agenda/turno/<int:pk>/editar/', views.turno_editar, name='turno_editar'),
    path('dashboard/agenda/turno/<int:pk>/cancelar/', views.turno_cancelar, name='turno_cancelar'),
    path('dashboard/agenda/turno/<int:pk>/repetir/', views.turno_repetir, name='turno_repetir'),
    # Recordatorios WhatsApp
    path('dashboard/recordatorios/', views.recordatorios_hoy, name='recordatorios_hoy'),

    # ── Turnero online: configuracion (dashboard) ────────────────────────
    path('dashboard/turnero/', views_turnero.turnero_config, name='turnero_config'),
    path('dashboard/turnero/franja/agregar/', views_turnero.franja_agregar, name='franja_agregar'),
    path('dashboard/turnero/franja/<int:pk>/eliminar/', views_turnero.franja_eliminar, name='franja_eliminar'),
    path('dashboard/turnero/bloqueo/agregar/', views_turnero.bloqueo_agregar, name='bloqueo_agregar'),
    path('dashboard/turnero/bloqueo/<int:pk>/eliminar/', views_turnero.bloqueo_eliminar, name='bloqueo_eliminar'),
    path('dashboard/turnero/mp/conectar/', views_turnero.mp_conectar, name='mp_conectar'),
    path('dashboard/turnero/mp/desconectar/', views_turnero.mp_desconectar, name='mp_desconectar'),
    path('turnero/mp/callback/', views_turnero.mp_callback, name='mp_callback'),

    # ── Turnero online: reserva publica (paciente, sin login) ────────────
    path('reservar/<slug:slug>/', views_turnero.turnero_reservar, name='turnero_reservar'),
    path('turnero/turno/<uuid:token>/', views_turnero.turnero_reservado, name='turnero_reservado'),
    path('turnero/turno/<uuid:token>/pagar/', views_turnero.turnero_pagar, name='turnero_pagar'),
    path('turnero/pago/<uuid:token>/retorno/', views_turnero.turnero_pago_retorno, name='turnero_pago_retorno'),
    path('turnero/turno/<uuid:token>/cancelar/', views_turnero.turnero_cancelar_publico, name='turnero_cancelar_publico'),
    path('turnero/turno/<uuid:token>/confirmar/', views_turnero.turno_confirmar_publico, name='turno_confirmar_publico'),
    path('turnero/mp/webhook/', views_turnero.mp_webhook, name='mp_webhook'),

    # ── Portal del paciente (login propio con DNI) ───────────────────────
    path('portal/login/', views_portal.portal_login, name='portal_login'),
    path('portal/seleccionar/', views_portal.portal_seleccionar_perfil, name='portal_seleccionar_perfil'),
    path('portal/logout/', views_portal.portal_logout, name='portal_logout'),
    path('portal/cambiar-password/', views_portal.portal_cambiar_password, name='portal_cambiar_password'),
    path('portal/', views_portal.portal_dashboard, name='portal_dashboard'),

    # ── Panel del dueño de la plataforma (solo superusuarios) ─────────────
    path('mi-panel/', views_panel.panel_resumen, name='panel_resumen'),
    path('mi-panel/egresos/<int:pk>/eliminar/', views_panel.panel_egreso_eliminar, name='panel_egreso_eliminar'),
    path('mi-panel/nutricionistas/', views_panel.panel_nutricionistas, name='panel_nutricionistas'),
    path('mi-panel/nutricionistas/nuevo/', views_panel.panel_nutricionista_nuevo, name='panel_nutricionista_nuevo'),
    path('mi-panel/nutricionistas/<int:pk>/editar/', views_panel.panel_nutricionista_editar, name='panel_nutricionista_editar'),
    path('mi-panel/nutricionistas/<int:pk>/cambiar-password/', views_panel.panel_nutricionista_cambiar_password, name='panel_nutricionista_cambiar_password'),
    path('mi-panel/nutricionistas/<int:pk>/tarjeta/', views_panel.panel_nutricionista_tarjeta, name='panel_nutricionista_tarjeta'),
    path('mi-panel/nutricionistas/<int:pk>/toggle/', views_panel.panel_nutricionista_toggle_aprobado, name='panel_nutricionista_toggle_aprobado'),
    path('mi-panel/nutricionistas/<int:pk>/toggle-destacado/', views_panel.panel_nutricionista_toggle_destacado, name='panel_nutricionista_toggle_destacado'),
    path('mi-panel/nutricionistas/<int:pk>/toggle-exento/', views_panel.panel_nutricionista_toggle_exento, name='panel_nutricionista_toggle_exento'),
    path('mi-panel/nutricionistas/<int:pk>/eliminar/', views_panel.panel_nutricionista_eliminar, name='panel_nutricionista_eliminar'),
    path('mi-panel/nutricionistas/reparar-logins/', views_panel.panel_reparar_logins, name='panel_reparar_logins'),
    path('mi-panel/pacientes/', views_panel.panel_pacientes, name='panel_pacientes'),
    path('mi-panel/pacientes/<int:pk>/blanquear-password/', views_panel.panel_paciente_blanquear_password, name='panel_paciente_blanquear_password'),
    path('mi-panel/leads/', views_panel.panel_leads, name='panel_leads'),
    path('mi-panel/leads/<int:pk>/toggle-contactado/', views_panel.panel_lead_toggle_contactado, name='panel_lead_toggle_contactado'),
    path('mi-panel/codigos/', views_panel.panel_codigos, name='panel_codigos'),
    path('mi-panel/codigos/nuevo/', views_panel.panel_codigo_nuevo, name='panel_codigo_nuevo'),
    path('mi-panel/codigos/<int:pk>/editar/', views_panel.panel_codigo_editar, name='panel_codigo_editar'),
]
