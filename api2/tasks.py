from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from .models import Song
import magic
from tinytag import TinyTag
import logging
import os
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def process_uploaded_song(self, song_id):
    """
    Tarea asíncrona para procesar archivos de audio subidos:
    - Extraer metadatos
    - Generar miniaturas
    - Validar formato
    """
    try:
        song = Song.objects.get(pk=song_id)
        
        # 1. Extraer metadatos del audio
        audio_metadata = extract_audio_metadata(song.file.path)
        
        # Actualizar campos si no estaban definidos
        updates = {}
        if not song.title and audio_metadata.get('title'):
            updates['title'] = audio_metadata['title'][:255]
        
        if not song.artist and audio_metadata.get('artist'):
            updates['artist'] = audio_metadata['artist'][:255]
        
        if audio_metadata.get('duration'):
            updates['duration'] = int(audio_metadata['duration'])
        
        if updates:
            Song.objects.filter(pk=song_id).update(**updates)
            song.refresh_from_db()
        
        # 2. Procesamiento adicional (opcional)
        # generate_audio_waveform(song)
        # generate_audio_thumbnail(song)
        
    except Song.DoesNotExist:
        logger.error(f"Canción {song_id} no existe")
    except Exception as e:
        logger.error(f"Error procesando canción {song_id}: {str(e)}")
        raise self.retry(exc=e, countdown=60)

def extract_audio_metadata(file_path):
    """Extrae metadatos de archivos de audio"""
    try:
        tag = TinyTag.get(file_path)
        return {
            'title': tag.title,
            'artist': tag.artist,
            'duration': tag.duration,
            'bitrate': tag.bitrate,
            'genre': tag.genre
        }
    except Exception as e:
        logger.warning(f"Error extrayendo metadatos: {str(e)}")
        return {}

# Otras tareas útiles
@shared_task
def cleanup_orphaned_files():
    """
    Elimina archivos huérfanos (en disco pero sin modelo asociado).
    Solo borra en `media/songs/` y `media/images/`
    """
    from django.conf import settings

    song_files = set(Song.objects.exclude(file='').values_list('file', flat=True))
    image_files = set(Song.objects.exclude(image='').values_list('image', flat=True))

    song_dir = os.path.join(settings.MEDIA_ROOT, 'songs')
    image_dir = os.path.join(settings.MEDIA_ROOT, 'images')

    # Helper para recorrer subdirectorios
    def collect_files(path):
        all_files = set()
        for root, dirs, files in os.walk(path):
            for file in files:
                rel_path = os.path.relpath(os.path.join(root, file), settings.MEDIA_ROOT)
                all_files.add(rel_path.replace('\\', '/'))  # normaliza separador
        return all_files

    # Detectar archivos no referenciados
    all_song_files = collect_files(song_dir)
    all_image_files = collect_files(image_dir)

    orphaned_songs = all_song_files - song_files
    orphaned_images = all_image_files - image_files

    for orphan_path in orphaned_songs | orphaned_images:
        full_path = os.path.join(settings.MEDIA_ROOT, orphan_path)
        try:
            os.remove(full_path)
            logger.info(f"Archivo huérfano eliminado: {orphan_path}")
        except Exception as e:
            logger.warning(f"No se pudo eliminar archivo {orphan_path}: {e}")

@shared_task
def convert_audio_format(song_id, target_format='mp3'):
    """Convierte audio a otro formato (requiere ffmpeg)"""
    pass

@shared_task
def verify_song_files():
    for song in Song.objects.exclude(file__isnull=True).iterator():
        if not default_storage.exists(song.file.name):
            logger.warning(f"Archivo perdido para la canción {song.id}")
            song.file = None
            song.save()
