from celery import shared_task
from django.utils import timezone
from .models import Transferencia, Recarga, Agente
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def ejecutar_transferencia_programada(self, transferencia_id):
    """
    Tarea Celery para ejecutar transferencias programadas
    """
    try:
        transferencia = Transferencia.objects.get(pk=transferencia_id)
        if transferencia.estado == Transferencia.Estados.PROGRAMADA:
            if transferencia.fecha_programada <= timezone.now():
                transferencia.procesar()
                logger.info(f"Transferencia programada {transferencia.referencia} procesada")
                return True
    except Exception as e:
        logger.error(f"Error procesando transferencia programada {transferencia_id}: {str(e)}")
        self.retry(exc=e, countdown=60)

@shared_task(bind=True, max_retries=3)
def procesar_recarga_async(self, recarga_id):
    """
    Tarea Celery para procesar recargas de forma asíncrona
    """
    try:
        recarga = Recarga.objects.get(pk=recarga_id)
        if recarga.estado == Recarga.Estados.PENDIENTE:
            # Lógica para encontrar agente disponible
            agente = Agente.objects.filter(activo=True).first()
            if agente:
                recarga.procesar(agente)
                logger.info(f"Recarga {recarga.referencia} procesada por agente {agente.codigo_agente}")
                return True
    except Exception as e:
        logger.error(f"Error procesando recarga {recarga_id}: {str(e)}")
        self.retry(exc=e, countdown=60)