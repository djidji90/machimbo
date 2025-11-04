from django.db import models
from django.core.validators import FileExtensionValidator
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.exceptions import ValidationError
import os
from pathlib import Path

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

        # VALIDACIÓN SIMPLIFICADA - SIN MAGIC
        if self.file:
            # Validación de tamaño
            if self.file.size > 20 * 1024 * 1024:
                raise ValidationError("El archivo excede el límite de 20MB")

            # Validación de extensión
            file_ext = os.path.splitext(self.file.name)[1].lower()
            allowed_audio_extensions = ['.mp3', '.wav', '.ogg', '.webm', '.m4a', '.mp4']
            if file_ext not in allowed_audio_extensions:
                raise ValidationError(f"Extensión {file_ext} no permitida. Use: {', '.join(allowed_audio_extensions)}")

        # Validación de imagen
        if self.image:
            max_image_size = 2 * 1024 * 1024  # 2MB
            if self.image.size > max_image_size:
                raise ValidationError("La imagen no puede exceder los 2MB")

            # Validación de extensión de imagen
            image_ext = os.path.splitext(self.image.name)[1].lower()
            allowed_image_extensions = ['.jpg', '.jpeg', '.png', '.webp']
            if image_ext not in allowed_image_extensions:
                raise ValidationError(f"Extensión de imagen {image_ext} no permitida. Use: {', '.join(allowed_image_extensions)}")

    def save(self, *args, **kwargs):
        self.full_clean()  # Ejecuta las validaciones antes de guardar
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Eliminar archivos físicos al borrar la instancia
        if self.file and default_storage.exists(self.file.name):
            default_storage.delete(self.file.name)
        if self.image and default_storage.exists(self.image.name):
            default_storage.delete(self.image.name)
        super().delete(*args, **kwargs)
    
    def file_exists(self):
        return self.file and default_storage.exists(self.file.name)

    class Meta:
        verbose_name = "Canción"
        verbose_name_plural = "Canciones"

class Like(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    song = models.ForeignKey(Song, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'song')
        verbose_name = "Me gusta"
        verbose_name_plural = "Me gusta"

    def __str__(self):
        return f"{self.user.username} likes {self.song.title}"

class Download(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    song = models.ForeignKey(Song, on_delete=models.CASCADE)
    downloaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Descarga"
        verbose_name_plural = "Descargas"

    def __str__(self):
        return f"{self.user.username} downloaded {self.song.title} on {self.downloaded_at}"

class Comment(models.Model):
    song = models.ForeignKey(Song, related_name="comments", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="comments", on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Comentario"
        verbose_name_plural = "Comentarios"

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
        verbose_name = "Reacción a comentario"
        verbose_name_plural = "Reacciones a comentarios"

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
        verbose_name = "Evento musical"
        verbose_name_plural = "Eventos musicales"