from django.db import models
from django.core.validators import FileExtensionValidator
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.exceptions import ValidationError
import os
from pathlib import Path

# SOLUCIÓN SEGURA PARA MAGIC - NO FALLARÁ EN DEPLOY
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    # Si magic no está disponible, crear un objeto dummy
    class MagicMock:
        def from_buffer(self, *args, **kwargs):
            return "application/octet-stream"
        def from_file(self, *args, **kwargs):
            return "application/octet-stream"
    magic = MagicMock()
    MAGIC_AVAILABLE = False

class Song(models.Model):
    """
    Modelo para representar canciones subidas por usuarios.
    """
    title = models.CharField(max_length=255)
    artist = models.CharField(max_length=255)
    genre = models.CharField(max_length=100)
    
    file = models.FileField(
        upload_to='songs/%Y/%m/%d/',
        help_text="Formatos soportados: MP3, WAV, OGG, WEBM (solo audio), M4A. Tamaño máximo: 20MB"
    )
    image = models.ImageField(
        upload_to='images/%Y/%m/%d/',
        help_text="Formatos soportados: JPG, PNG, WEBP. Tamaño máximo: 2MB",
        blank=True,
        null=True
    )
    duration = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Duración de la canción en segundos"
    )
    likes_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='songs',
        null=True,
        blank=True,
        help_text="Usuario que subió la canción"
    )

    def __str__(self):
        return f"{self.title} by {self.artist}"

    def clean(self):
        super().clean()

        if self.file:
            # Validación de tamaño
            if self.file.size > 20 * 1024 * 1024:
                raise ValidationError("El archivo excede el límite de 20MB")

            # Validación de extensión
            file_ext = os.path.splitext(self.file.name)[1].lower()
            if file_ext not in ['.mp3', '.wav', '.ogg', '.webm', '.m4a', '.mp4']:
                raise ValidationError(f"Extensión {file_ext} no permitida")

            # Validación MIME (solo si magic está disponible)
            if MAGIC_AVAILABLE:
                try:
                    self.file.seek(0)
                    header = self.file.read(1024)
                    self.file.seek(0)
                    
                    mime_type = magic.from_buffer(header, mime=True)
                    
                    # Normalización
                    if mime_type in ['video/webm', 'audio/webm']:
                        mime_type = 'audio/webm'
                    elif mime_type in ['video/mp4', 'audio/x-m4a', 'audio/mp4']:
                        mime_type = 'audio/mp4'

                    # Validación final
                    if mime_type not in ['audio/mpeg', 'audio/wav', 'audio/ogg', 
                                       'audio/webm', 'audio/mp4']:
                        raise ValidationError(
                            f"Formato detectado: {mime_type}. "
                            "Solo se aceptan archivos de audio puro (sin video)"
                        )
                except Exception as e:
                    print(f"Advertencia: Error en validación MIME: {e}")

        # Validación de imagen
        if self.image:
            max_image_size = 2 * 1024 * 1024  # 2MB
            if self.image.size > max_image_size:
                raise ValidationError("La imagen no puede exceder los 2MB")

            # Validación MIME de imagen (solo si magic está disponible)
            if MAGIC_AVAILABLE:
                try:
                    self.image.seek(0)
                    image_type = magic.from_buffer(self.image.read(1024), mime=True)
                    self.image.seek(0)

                    allowed_image_types = [
                        'image/jpeg',
                        'image/png',
                        'image/webp'
                    ]

                    if image_type not in allowed_image_types:
                        raise ValidationError(
                            f"Formato de imagen no soportado: {image_type}. "
                            f"Permitidos: JPG, PNG, WEBP."
                        )
                except Exception as e:
                    print(f"Advertencia: No se pudo verificar el tipo de imagen: {e}")

    def save(self, *args, **kwargs):
        self.full_clean()  # Ejecuta las validaciones antes de guardar
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Eliminar archivos físicos al borrar la instancia
        if self.file and os.path.isfile(self.file.path):
            os.remove(self.file.path)
        if self.image and os.path.isfile(self.image.path):
            os.remove(self.image.path)
        super().delete(*args, **kwargs)
    
    def file_exists(self):
        return self.file and default_storage.exists(self.file.name)

# Los demás modelos permanecen igual...
class Like(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    song = models.ForeignKey(Song, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'song')

    def __str__(self):
        return f"{self.user.username} likes {self.song.title}"

class Download(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    song = models.ForeignKey(Song, on_delete=models.CASCADE)
    downloaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} downloaded {self.song.title} on {self.downloaded_at}"

class Comment(models.Model):
    song = models.ForeignKey(Song, related_name="comments", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="comments", on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.song.title}"

    def clean(self):
        if len(self.content.strip()) == 0:
            raise ValidationError("El comentario no puede estar vacío.")

class CommentReaction(models.Model):
    comment = models.ForeignKey(Comment, related_name="reactions", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="reactions", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('comment', 'user')

class MusicEvent(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    event_date = models.DateTimeField()
    location = models.CharField(max_length=255)
    image = models.ImageField(upload_to='events/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-event_date']