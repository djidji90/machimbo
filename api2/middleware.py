# middleware.py

from django.core.exceptions import MiddlewareNotUsed
from django.http import Http404
from rest_framework.exceptions import NotFound
from .models import Song
from .views import DownloadSongView  # Asegúrate de importar correctamente

class SongFileCheckMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        # Solo aplicamos la lógica si es la vista de descarga
        if hasattr(view_func, 'view_class') and view_func.view_class == DownloadSongView:
            song_id = view_kwargs.get('song_id')
            if song_id:
                try:
                    song = Song.objects.get(id=song_id)
                    if not song.file_exists():
                        raise NotFound("El archivo de audio no está disponible.")
                except Song.DoesNotExist:
                    raise NotFound("Canción no encontrada.")
