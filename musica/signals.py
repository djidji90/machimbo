from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from monedero.models import Monedero  # <-- Importar desde la app correcta

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def crear_monedero_automatico(sender, instance, created, **kwargs):
    """
    Crea automáticamente un Monedero para cada nuevo usuario registrado.
    """
    if created:
        try:
            Monedero.objects.get_or_create(usuario=instance)
        except Exception as e:
            # Aquí puedes loguear el error si usas logging
            print(f"Error creando monedero para el usuario {instance.id}: {e}")
