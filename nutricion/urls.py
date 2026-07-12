from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.views.static import serve as static_serve
from django.views.generic import TemplateView
from core.forms import LoginForm, PasswordChangeStyledForm

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path('robots.txt', TemplateView.as_view(
        template_name='robots.txt', content_type='text/plain',
        extra_context={'admin_url': settings.ADMIN_URL},
    )),
    path('', include('core.urls')),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html', authentication_form=LoginForm), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    # Cambiar contraseña estando ya logueado (nutricionista) — distinto del
    # portal_cambiar_password del paciente, que tiene su propio flujo.
    path('dashboard/cambiar-password/',
         auth_views.PasswordChangeView.as_view(
             template_name='dashboard/password_change_form.html',
             form_class=PasswordChangeStyledForm,
         ),
         name='password_change'),
    path('dashboard/cambiar-password/hecho/',
         auth_views.PasswordChangeDoneView.as_view(template_name='dashboard/password_change_done.html'),
         name='password_change_done'),
    # Recuperacion de contrasena
    path('password-reset/',
         auth_views.PasswordResetView.as_view(
             template_name='registration/password_reset_form.html',
             email_template_name='registration/password_reset_email.html',
             subject_template_name='registration/password_reset_subject.txt',
         ),
         name='password_reset'),
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='registration/password_reset_done.html',
         ),
         name='password_reset_done'),
    path('password-reset/confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='registration/password_reset_confirm.html',
         ),
         name='password_reset_confirm'),
    path('password-reset/complete/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='registration/password_reset_complete.html',
         ),
         name='password_reset_complete'),

    # Fotos de perfil de nutricionistas: son públicas por diseño (se muestran
    # en el directorio), así que se sirven directo, sin login, sin importar
    # DEBUG. Los archivos clínicos (laboratorios, planes, archivos de
    # pacientes) NO se sirven acá — pasan por vistas autenticadas en
    # core/views.py, para que nadie pueda verlos solo por adivinar la URL.
    path(
        'media/nutricionistas/<path:path>',
        static_serve,
        {'document_root': str(settings.MEDIA_ROOT / 'nutricionistas')},
    ),
]
