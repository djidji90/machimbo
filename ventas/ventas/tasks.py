from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q, Count
import logging

from ventas.models import (
    Pedido,
    Producto,
    TransaccionRetenida,
    EstadoPedido,  # Asegúrate de que esto exista en tus models.py
)

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def liberar_fondos_retenidos(self):
    """
    Task to release held funds after retention period
    """
    try:
        now = timezone.now()
        retenciones = TransaccionRetenida.objects.filter(
            estado='VERIFICADA',
            fecha_liberacion__lte=now
        )
        
        for retencion in retenciones:
            try:
                if retencion.liberar_fondos():
                    logger.info(f"Fondos liberados para {retencion.referencia}")
                else:
                    logger.warning(f"No se pudo liberar fondos para {retencion.referencia}")
            except Exception as e:
                logger.error(f"Error liberando fondos {retencion.referencia}: {str(e)}")
                continue
        
        return f"Procesadas {len(retenciones)} retenciones"
    except Exception as e:
        logger.error(f"Error en tarea liberar_fondos_retenidos: {str(e)}")
        raise self.retry(exc=e, countdown=60)

@shared_task
def verificar_stock_pedidos_pendientes():
    """
    Check stock for pending orders and notify if any problems
    """
    pedidos = Pedido.objects.filter(estado=EstadoPedido.PAGO_PENDIENTE)
    
    for pedido in pedidos:
        try:
            stock_ok, mensaje = pedido.verificar_stock()
            if not stock_ok:
                # In a real implementation, notify admin/user
                logger.warning(f"Problema de stock en pedido {pedido.id}: {mensaje}")
        except Exception as e:
            logger.error(f"Error verificando stock pedido {pedido.id}: {str(e)}")

@shared_task
def enviar_recordatorio_verificacion():
    """
    Send verification code reminders
    """
    limite_tiempo = timezone.now() - timedelta(hours=6)
    pedidos = Pedido.objects.filter(
        estado=EstadoPedido.VERIFICACION_PENDIENTE,
        fecha_creacion__lte=limite_tiempo
    )
    
    for pedido in pedidos:
        # In a real implementation, this would send an email/SMS
        logger.info(f"Recordatorio enviado para verificar pedido {pedido.id}")

@shared_task
def actualizar_productos_destacados():
    """
    Periodic task to update featured products based on business logic
    """
    productos_destacados = Producto.objects.annotate(
        num_pedidos=Count('items__pedido', filter=Q(
            items__pedido__fecha_creacion__gte=timezone.now() - timedelta(days=30))
        )
    ).order_by('-num_pedidos', '-fecha_creacion')[:10]
    
    # Update all products
    Producto.objects.update(destacado=False)
    productos_destacados.update(destacado=True)
    
    return f"Actualizados {len(productos_destacados)} productos destacados"
