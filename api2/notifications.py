from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from .models import Song, Comment
import logging
from django.utils.html import strip_tags


logger = logging.getLogger(__name__)

# Configuración
AUDIO_UPLOAD_NOTIFY_ADMINS = getattr(settings, 'AUDIO_UPLOAD_NOTIFY_ADMINS', True)
COMMENT_NOTIFY_AUTHOR = getattr(settings, 'COMMENT_NOTIFY_AUTHOR', True)

@receiver(post_save, sender=Song)
def handle_song_upload(sender, instance, created, **kwargs):
    """Maneja notificaciones cuando se sube una nueva canción"""
    if created:
        try:
            # Notificación al usuario que subió la canción
            send_upload_confirmation(instance)
            
            # Notificación a administradores
            if AUDIO_UPLOAD_NOTIFY_ADMINS:
                notify_admins_new_song(instance)
                
        except Exception as e:
            logger.error(f"Error en notificación de subida: {e}")

@receiver(post_save, sender=Comment)
def handle_new_comment(sender, instance, created, **kwargs):
    """Notifica al autor de la canción sobre nuevos comentarios"""
    if created and COMMENT_NOTIFY_AUTHOR:
        try:
            if instance.song.uploaded_by and instance.user != instance.song.uploaded_by:
                notify_comment_to_author(instance)
        except Exception as e:
            logger.error(f"Error en notificación de comentario: {e}")

def send_upload_confirmation(song):
    """Envía confirmación al usuario que subió la canción"""
    subject = f"✅ Canción subida: {song.title}"
    context = {
        'song': song,
        'user': song.uploaded_by
    }
    
    send_email(
        subject=subject,
        template='emails/song_upload_confirmation.html',
        context=context,
        to_emails=[song.uploaded_by.email]
    )

def notify_admins_new_song(song):
    """Notifica a los administradores sobre nueva canción"""
    subject = f"🎵 Nueva canción subida: {song.title}"
    admin_url = f"{settings.SITE_URL}/admin/music/song/{song.id}/change/"
    
    send_email(
        subject=subject,
        template='emails/admin_new_song_notification.html',
        context={'song': song, 'admin_url': admin_url},
        to_emails=get_admin_emails()
    )

def notify_comment_to_author(comment):
    """Notifica al autor sobre nuevo comentario"""
    subject = f"💬 Nuevo comentario en tu canción: {comment.song.title}"
    
    send_email(
        subject=subject,
        template='emails/new_comment_notification.html',
        context={'comment': comment},
        to_emails=[comment.song.uploaded_by.email]
    )

# Funciones de apoyo
def send_email(subject, template, context, to_emails):
    """Función genérica para enviar emails"""
    if not settings.EMAIL_NOTIFICATIONS_ENABLED:
        return
        
    html_content = render_to_string(template, context)
    plain_message = strip_tags(html_content)
    
    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=to_emails,
        html_message=html_content,
        fail_silently=False
    )

def get_admin_emails():
    """Obtiene emails de todos los administradores"""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.filter(
        is_staff=True, 
        is_active=True
    ).values_list('email', flat=True)