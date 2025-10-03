import logging
import json
from django.db.models.signals import post_save, pre_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.db import transaction
from django.db.models.functions import Cast
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.utils.functional import LazyObject
from django.contrib.auth.models import AnonymousUser
import threading
from .models import (
    Pedido, ItemPedido, Producto, VarianteProducto,
    TransaccionRetenida, Proveedor, ImagenProducto, 
    ImagenVarianteProducto, Auditoria, Notificacion
)
from .models import EstadoPedido
from .services import NotificacionService

logger = logging.getLogger(__name__)
thread_local = threading.local()

# ==================== UTILITY FUNCTIONS ====================
def get_current_user():
    """Obtiene el usuario actual desde el thread local"""
    user = getattr(thread_local, 'user', None)
    
    if isinstance(user, LazyObject):
        user = user._wrapped
    
    if user is None or isinstance(user, AnonymousUser):
        return None
    
    return user

def get_client_ip():
    """Obtiene la IP del cliente desde la request"""
    request = getattr(thread_local, 'request', None)
    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        return x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')
    return None

def log_auditoria(modelo, instancia, accion, cambios=None):
    """Registra una acción en el sistema de auditoría"""
    user = get_current_user()
    
    datos_antes = cambios.get('antes') if cambios else None
    datos_despues = cambios.get('despues') if cambios else None
    
    Auditoria.objects.create(
        usuario=user,
        modelo=modelo,
        objeto_id=instancia.pk,
        accion=accion,
        datos_antes=datos_antes,
        datos_despues=datos_despues,
        ip=get_client_ip(),
        fecha=timezone.now()
    )

# ==================== PRODUCTO SIGNALS ====================
@receiver(pre_save, sender=Producto)
def producto_pre_save(sender, instance, **kwargs):
    """Valida y audita cambios en productos"""
    if instance.pk:
        original = Producto.objects.get(pk=instance.pk)
        cambios = {}
        
        # Verificar cambios importantes
        for field in ['precio', 'stock', 'disponible']:
            original_val = getattr(original, field)
            nuevo_val = getattr(instance, field)
            if original_val != nuevo_val:
                cambios[field] = {
                    'antes': original_val,
                    'despues': nuevo_val
                }
                
                # Notificar si stock bajo
                if field == 'stock' and nuevo_val < 10:
                    NotificacionService.crear_notificacion(
                        usuario=get_current_user() or instance.proveedor.usuario,
                        tipo='stock_bajo',
                        contexto={
                            'producto': instance.nombre,
                            'stock_actual': nuevo_val
                        }
                    )
        
        if cambios:
            log_auditoria(
                modelo='Producto',
                instancia=instance,
                accion='modificar',
                cambios={'datos': cambios}
            )

@receiver(post_save, sender=Producto)
def producto_post_save(sender, instance, created, **kwargs):
    """Registra creación de nuevos productos"""
    if created:
        log_auditoria(
            modelo='Producto',
            instancia=instance,
            accion='crear',
            cambios={'datos': instance.__dict__}
        )

@receiver(post_delete, sender=Producto)
def producto_post_delete(sender, instance, **kwargs):
    """Registra eliminación de productos"""
    log_auditoria(
        modelo='Producto',
        instancia=instance,
        accion='eliminar',
        cambios={'datos': instance.__dict__}
    )

# ==================== IMAGENES SIGNALS ====================
@receiver(post_delete, sender=ImagenProducto)
def auto_set_new_principal_product_image(sender, instance, **kwargs):
    """
    Cuando se elimina la imagen principal, establece otra imagen como principal
    """
    if instance.es_principal and instance.producto.imagenes.exists():
        with transaction.atomic():
            new_principal = instance.producto.imagenes.first()
            new_principal.es_principal = True
            new_principal.save()
            
            log_auditoria(
                modelo='ImagenProducto',
                instancia=instance.producto,
                accion='modificar',
                cambios={
                    'mensaje': f'Se estableció nueva imagen principal para producto {instance.producto.id}'
                }
            )

@receiver(post_delete, sender=ImagenVarianteProducto)
def auto_set_new_principal_variant_image(sender, instance, **kwargs):
    """
    Cuando se elimina la imagen principal de variante, establece otra como principal
    """
    if instance.es_principal and instance.variante.imagenes_variante.exists():
        with transaction.atomic():
            new_principal = instance.variante.imagenes_variante.first()
            new_principal.es_principal = True
            new_principal.save()
            
            log_auditoria(
                modelo='ImagenVarianteProducto',
                instancia=instance.variante,
                accion='modificar',
                cambios={
                    'mensaje': f'Se estableció nueva imagen principal para variante {instance.variante.id}'
                }
            )

# ==================== PEDIDO SIGNALS ====================
@receiver(pre_save, sender=Pedido)
def validate_order_status_change(sender, instance, **kwargs):
    """
    Valida transiciones de estado del pedido y registra cambios
    """
    if instance.pk:
        original = Pedido.objects.get(pk=instance.pk)
        
        # Registrar cambio de estado
        if original.estado != instance.estado:
            log_auditoria(
                modelo='Pedido',
                instancia=instance,
                accion='modificar_estado',
                cambios={
                    'antes': original.estado,
                    'despues': instance.estado
                }
            )
            
            # Notificaciones según estado
            if instance.estado == EstadoPedido.VERIFICADO:
                NotificacionService.crear_notificacion(
                    usuario=instance.usuario,
                    tipo='pedido_verificado',
                    contexto={
                        'pedido_id': instance.id,
                        'fecha': instance.fecha_verificacion.strftime('%d/%m/%Y %H:%M')
                    }
                )
            elif instance.estado == EstadoPedido.CANCELADO:
                NotificacionService.crear_notificacion(
                    usuario=instance.usuario,
                    tipo='pedido_cancelado',
                    contexto={
                        'pedido_id': instance.id,
                        'motivo': getattr(instance, 'motivo_cancelacion', 'No especificado')
                    }
                )

        # Validar transiciones no permitidas
        invalid_transitions = {
            EstadoPedido.COMPLETADO: [EstadoPedido.PENDIENTE, EstadoPedido.PAGO_PENDIENTE],
            EstadoPedido.CANCELADO: [EstadoPedido.COMPLETADO, EstadoPedido.ENVIADO]
        }
        
        for invalid_status, from_statuses in invalid_transitions.items():
            if instance.estado == invalid_status and original.estado in from_statuses:
                error_msg = f"No se puede cambiar de {original.estado} a {invalid_status}"
                logger.error(error_msg)
                raise ValidationError(error_msg)

@receiver(post_save, sender=Pedido)
def handle_new_order(sender, instance, created, **kwargs):
    """Maneja la creación de nuevos pedidos"""
    if created:
        log_auditoria(
            modelo='Pedido',
            instancia=instance,
            accion='crear',
            cambios={'datos': instance.__dict__}
        )
        
        # Notificar creación de pedido
        NotificacionService.crear_notificacion(
            usuario=instance.usuario,
            tipo='pedido_creado',
            contexto={
                'pedido_id': instance.id,
                'total': instance.total,
                'fecha': instance.fecha_creacion.strftime('%d/%m/%Y %H:%M')
            }
        )

# ==================== ITEM PEDIDO SIGNALS ====================
@receiver(post_save, sender=ItemPedido)
def update_order_totals(sender, instance, created, **kwargs):
    """
    Actualiza totales del pedido cuando se añaden/modifican items
    """
    if created or instance.pedido.estado == EstadoPedido.PENDIENTE:
        with transaction.atomic():
            instance.pedido.calcular_totales()
            
            log_auditoria(
                modelo='ItemPedido',
                instancia=instance.pedido,
                accion='actualizar_totales',
                cambios={
                    'item_id': instance.id,
                    'cantidad': instance.cantidad,
                    'subtotal': instance.subtotal
                }
            )

# ==================== PROVEEDOR SIGNALS ====================
@receiver(post_save, sender=Proveedor)
def create_supplier_wallet(sender, instance, created, **kwargs):
    """
    Crea un monedero cuando se registra un nuevo proveedor
    """
    if created and instance.usuario:
        with transaction.atomic():
            from monedero.models import Monedero
            Monedero.objects.get_or_create(usuario=instance.usuario)
            logger.info(f"Monedero creado para proveedor {instance.nombre}")
            
            log_auditoria(
                modelo='Proveedor',
                instancia=instance,
                accion='crear_monedero',
                cambios={'usuario': instance.usuario.username}
            )

# ==================== TRANSACCIONES SIGNALS ====================
@receiver(pre_save, sender=TransaccionRetenida)
def generate_verification_code(sender, instance, **kwargs):
    """
    Genera código de verificación para nuevas transacciones
    """
    if not instance.codigo_verificacion:
        from django.utils.crypto import get_random_string
        instance.codigo_verificacion = get_random_string(8, '0123456789')
        
        log_auditoria(
            modelo='TransaccionRetenida',
            instancia=instance,
            accion='generar_codigo',
            cambios={'codigo': instance.codigo_verificacion}
        )

@receiver(post_save, sender=TransaccionRetenida)
def notify_supplier_on_verification(sender, instance, created, **kwargs):
    """
    Notifica al proveedor cuando los fondos están verificados y listos para liberación
    """
    if instance.estado == 'VERIFICADA' and not created:
        logger.info(f"Fondos verificados para transacción {instance.referencia}")
        
        # Notificar al proveedor
        if instance.proveedor and instance.proveedor.usuario:
            NotificacionService.crear_notificacion(
                usuario=instance.proveedor.usuario,
                tipo='comision_verificada',
                contexto={
                    'monto': instance.monto,
                    'fecha_liberacion': instance.fecha_liberacion.strftime('%d/%m/%Y'),
                    'codigo': instance.codigo_verificacion
                }
            )
        
        log_auditoria(
            modelo='TransaccionRetenida',
            instancia=instance,
            accion='verificar_transaccion',
            cambios={'estado': 'VERIFICADA'}
        )

# ==================== MIDDLEWARE INTEGRATION ====================
class AuditMiddleware:
    """Middleware para capturar usuario y request actual"""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        thread_local.request = request
        thread_local.user = request.user if hasattr(request, 'user') else None
        response = self.get_response(request)
        return response