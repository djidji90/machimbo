from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings
import json

from monedero.models import Notificacion

class NotificacionService:
    @staticmethod
    def crear_notificacion(usuario, tipo, contexto=None):
        mensajes = {
            'pedido_creado': f'Pedido #{contexto.get("pedido_id")} creado exitosamente',
            'pedido_verificado': f'Pedido #{contexto.get("pedido_id")} verificado',
            'pedido_cancelado': f'Pedido #{contexto.get("pedido_id")} cancelado',
            'pago_aprobado': f'Pago por ${contexto.get("monto")} aprobado',
            'stock_bajo': f'Stock bajo para el producto {contexto.get("producto")}'
        }
        
        notificacion = Notificacion.objects.create(
            usuario=usuario,
            tipo=tipo,
            mensaje=mensajes.get(tipo, 'Nueva notificación'),
            metadata=contexto or {}
        )
        
        # Enviar email si es notificación importante
        if tipo in ['pedido_creado', 'pedido_cancelado', 'pago_aprobado']:
            NotificacionService.enviar_email(usuario, tipo, contexto)
            
        return notificacion

    @staticmethod
    def enviar_email(usuario, tipo, contexto):
        subject = f"Notificación: {tipo.replace('_', ' ').title()}"
        template = f'emails/{tipo}.html'
        
        context = {
            'usuario': usuario,
            **contexto
        }
        
        message = render_to_string(template, context)
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [usuario.email],
            html_message=message
        )