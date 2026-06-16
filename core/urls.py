from django.urls import path
from . import views

urlpatterns = [
    # Públicas
    path('', views.home, name='home'),
    path('registro/', views.registro, name='registro'),
    path('nutricionistas/<slug:slug>/', views.perfil_publico, name='perfil_publico'),

    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),

    # Perfil
    path('dashboard/perfil/', views.perfil_editar, name='perfil_editar'),

    # Pacientes
    path('dashboard/pacientes/', views.pacientes_lista, name='pacientes_lista'),
    path('dashboard/pacientes/nuevo/', views.paciente_nuevo, name='paciente_nuevo'),
    path('dashboard/pacientes/<int:pk>/editar/', views.paciente_editar, name='paciente_editar'),
    path('dashboard/pacientes/<int:pk>/archivar/', views.paciente_archivar, name='paciente_archivar'),

    # Agenda
    path('dashboard/agenda/', views.agenda, name='agenda'),
    path('dashboard/agenda/nuevo/', views.turno_nuevo, name='turno_nuevo'),
    path('dashboard/agenda/<int:pk>/editar/', views.turno_editar, name='turno_editar'),
    path('dashboard/agenda/<int:pk>/cancelar/', views.turno_cancelar, name='turno_cancelar'),
]
