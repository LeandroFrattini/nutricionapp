from django.urls import path
from . import views
from . import views_turnero

urlpatterns = [
    path('', views.home, name='home'),
    path('nutricionistas/', views.nutricionistas_lista, name='nutricionistas_lista'),
    path('nutricionistas/<slug:slug>/', views.perfil_publico, name='perfil_publico'),
    path('quiero-ser-parte/', views.quiero_ser_parte, name='quiero_ser_parte'),
    path('registro/', views.registro, name='registro'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/en-revision/', views.en_revision, name='en_revision'),
    path('dashboard/perfil/', views.perfil_editar, name='perfil_editar'),
    # Pacientes
    path('dashboard/pacientes/', views.pacientes_lista, name='pacientes_lista'),
    path('dashboard/pacientes/nuevo/', views.paciente_nuevo, name='paciente_nuevo'),
    path('dashboard/pacientes/<int:pk>/', views.paciente_detalle, name='paciente_detalle'),
    path('dashboard/pacientes/<int:pk>/editar/', views.paciente_editar, name='paciente_editar'),
    path('dashboard/pacientes/<int:pk>/archivar/', views.paciente_archivar, name='paciente_archivar'),
    # Mediciones
    path('dashboard/pacientes/<int:pk>/medicion/nueva/', views.medicion_nueva, name='medicion_nueva'),
    path('dashboard/pacientes/<int:pk>/medicion/<int:mid>/editar/', views.medicion_editar, name='medicion_editar'),
    # Laboratorio
    path('dashboard/pacientes/<int:pk>/laboratorio/nuevo/', views.laboratorio_nuevo, name='laboratorio_nuevo'),
    path('dashboard/pacientes/<int:pk>/laboratorio/<int:lid>/editar/', views.laboratorio_editar, name='laboratorio_editar'),
    # Plan alimentario
    path('dashboard/pacientes/<int:pk>/plan/nuevo/', views.plan_nuevo, name='plan_nuevo'),
    path('dashboard/pacientes/<int:pk>/plan/<int:pid>/editar/', views.plan_editar, name='plan_editar'),
    # Consultas
    path('dashboard/pacientes/<int:pk>/consulta/nueva/', views.consulta_nueva, name='consulta_nueva'),
    path('dashboard/pacientes/<int:pk>/consulta/<int:cid>/editar/', views.consulta_editar, name='consulta_editar'),
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
    path('turnero/mp/webhook/', views_turnero.mp_webhook, name='mp_webhook'),
]
