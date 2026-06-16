from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Turno
from .emails import enviar_confirmacion_turno


@receiver(post_save, sender=Turno)
def turno_guardado(sender, instance, created, **kwargs):
    """Envía mail de confirmación cada vez que se crea un turno."""
    if created and instance.estado == 'confirmado':
        enviar_confirmacion_turno(instance)
