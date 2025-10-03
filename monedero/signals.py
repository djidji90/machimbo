from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Monedero, User, Agente, Transferencia, Recarga
import logging

logger = logging.getLogger(__name__)


# signals.py


@receiver(post_save, sender=User)
def crear_monedero_usuario(sender, instance, created, **kwargs):
    """Crea monedero automáticamente para nuevos usuarios"""
    if created:
        try:
            Monedero.objects.create(
                usuario=instance,
                saldo=0,
                saldo_retenido=0,
                limite_credito=0,
                nivel_verificacion=1
            )
            logger.info(f"Monedero creado para usuario {instance.username}")
        except Exception as e:
            logger.error(f"Error al crear monedero: {str(e)}", exc_info=True)
            # Puede agregarse notificación al admin aquí

@receiver(post_save, sender=Agente)
def asignar_permisos_agente(sender, instance, created, **kwargs):
    """
    Asigna permisos específicos cuando se crea un agente
    """
    if created:
        instance.usuario.groups.add('agentes')
        instance.usuario.save()
        logger.info(f"Permisos de agente asignados a {instance.usuario.username}")

@receiver(pre_save, sender=Transferencia)
def validar_transferencia(sender, instance, **kwargs):
    """
    Validaciones previas al guardar una transferencia
    """
    if instance.estado == Transferencia.Estados.PENDIENTE:
        instance.clean()
        logger.debug(f"Transferencia {instance.referencia} validada")

@receiver(post_save, sender=Recarga)
def programar_procesamiento_recarga(sender, instance, created, **kwargs):
    """
    Inicia el procesamiento asíncrono de recargas si está configurado
    """
    if created and instance.estado == Recarga.Estados.PENDIENTE:
        from .tasks import procesar_recarga_async
        task = procesar_recarga_async.delay(instance.pk)
        instance.tarea_procesamiento = task.id
        instance.save(update_fields=['tarea_procesamiento'])
        logger.info(f"Recarga {instance.referencia} enviada a procesamiento asíncrono")

@receiver(post_save, sender=Transferencia)
def programar_transferencia(sender, instance, created, **kwargs):
    """
    Programa transferencias futuras si corresponde
    """
    if created and instance.estado == Transferencia.Estados.PROGRAMADA:
        instance.programar(instance.fecha_programada)
        logger.info(f"Transferencia {instance.referencia} programada para {instance.fecha_programada}")