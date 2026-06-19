"""
Comando para entorno de desarrollo.
Crea un perfil Nutricionista (premium, aprobado) para el primer superusuario.
Uso: python manage.py setup_dev
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Crea perfil Nutricionista para el superusuario (solo desarrollo)'

    def handle(self, *args, **options):
        from core.models import Nutricionista

        superusers = User.objects.filter(is_superuser=True)
        if not superusers.exists():
            self.stderr.write('No hay superusuarios. Crea uno primero con createsuperuser.')
            return

        for user in superusers:
            nutri, created = Nutricionista.objects.get_or_create(
                user=user,
                defaults={
                    'matricula': 'DEV-0001',
                    'bio': 'Perfil de desarrollo',
                    'aprobado': True,
                    'tipo': 'premium',
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(
                    f'Perfil creado para {user.username} (premium, aprobado).'
                ))
            else:
                # Asegurar que este aprobado y sea premium
                nutri.aprobado = True
                nutri.tipo = 'premium'
                nutri.save()
                self.stdout.write(self.style.SUCCESS(
                    f'Perfil de {user.username} actualizado a premium/aprobado.'
                ))
