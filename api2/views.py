
from datetime import timedelta
from time import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter  # Esta línea debe estar presente
from django.db import DatabaseError, IntegrityError
from rest_framework.exceptions import ValidationError
from django.db.models.functions import Lower
from django.db.models import Value, CharField
from rest_framework.response import Response
from rest_framework.response import Response
from rest_framework.decorators import api_view
from .models import Song
from django.core.files.storage import default_storage
from django.utils import timezone
from django.db.models import Q

from rest_framework.parsers import MultiPartParser, FormParser
import magic
from django.utils.text import slugify

from django.db.models import Max
from django.db.models import Sum
from .serializers import SongSerializer
from django.db.models import Q
from rest_framework.decorators import api_view
import logging
from rest_framework import generics, permissions
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.cache import cache
from django.db.models import Count, Q
from rest_framework.pagination import PageNumberPagination
from django.db import transaction
from .models import Song, Like, Download, Comment
from .serializers import SongSerializer, CommentSerializer
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.throttling import UserRateThrottle
from django.http import FileResponse, StreamingHttpResponse
from django.core.files.storage import default_storage
from drf_spectacular.utils import extend_schema, OpenApiParameter  # Importación requerida
import random
from rest_framework.filters import SearchFilter
from rest_framework import generics, permissions
from .models import MusicEvent
from .serializers import MusicEventSerializer
from rest_framework.response import Response
from rest_framework import status
import os
from django.db.models import Prefetch, Count

logger = logging.getLogger(__name__)





# En tu views.py

@extend_schema(
    description="Obtener sugerencias de búsqueda en tiempo real",
    parameters=[
        OpenApiParameter(name='query', description='Texto de búsqueda', required=True, type=str)
    ]
)
@api_view(['GET'])
def song_suggestions(request):
    query = request.GET.get('query', '').strip()[:100]
    
    if not query:
        return Response({"suggestions": []})
    
    # Búsqueda en múltiples campos con ponderación
    title_results = Song.objects.filter(
        Q(title__icontains=query)
    ).annotate(
        type=Value('song', output_field=CharField()),
        display=Lower('title')
    ).values('id', 'display', 'type', 'artist', 'genre')[:3]
    
    artist_results = Song.objects.filter(
        Q(artist__icontains=query)
    ).annotate(
        type=Value('artist', output_field=CharField()),
        display=Lower('artist')
    ).values('id', 'display', 'type', 'artist', 'genre').distinct()[:3]
    
    genre_results = Song.objects.filter(
        Q(genre__icontains=query)
    ).annotate(
        type=Value('genre', output_field=CharField()),
        display=Lower('genre')
    ).values('id', 'display', 'type', 'artist', 'genre').distinct()[:2]
    
    # Combinar resultados preservando el orden de relevancia
    suggestions = list(title_results) + list(artist_results) + list(genre_results)
    
    # Eliminar duplicados manteniendo el primer ocurrencia
    seen = set()
    unique_suggestions = []
    for s in suggestions:
        key = (s['display'], s['type'])
        if key not in seen:
            seen.add(key)
            unique_suggestions.append({
                "id": s['id'],
                "title": s['display'] if s['type'] == 'song' else None,
                "artist": s['artist'],
                "genre": s['genre'],
                "type": s['type'],
                "display": f"{s['display']} ({s['type']})"
            })
    
    return Response({"suggestions": unique_suggestions[:5]})






class CommentPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = 'page_size'
# Music Event List View
@extend_schema(description="Listar eventos de música")
class MusicEventListView(generics.ListCreateAPIView):
    queryset = MusicEvent.objects.all()
    serializer_class = MusicEventSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def handle_exception(self, exc):
        if isinstance(exc, (DatabaseError, IntegrityError)):
            logger.error(f"Database error in MusicEventListView: {exc}")
            return Response(
                {"error": "Error de base de datos al procesar eventos"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        return super().handle_exception(exc)

    def perform_create(self, serializer):
        try:
            serializer.save()
        except IntegrityError as e:
            logger.error(f"Integrity error creating event: {e}")
            raise ValidationError("Error de integridad en los datos del evento")
        except Exception as e:
            logger.error(f"Error creating event: {e}")
            raise ValidationError("Error inesperado al crear el evento")


# Music Event Detail View
@extend_schema(description="Obtener, actualizar o eliminar un evento de música")
class MusicEventDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = MusicEvent.objects.all()
    serializer_class = MusicEventSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def handle_exception(self, exc):
        if isinstance(exc, (DatabaseError, IntegrityError)):
            logger.error(f"Database error in MusicEventDetailView: {exc}")
            return Response(
                {"error": "Error de base de datos al procesar el evento"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        return super().handle_exception(exc)

    def perform_update(self, serializer):
        try:
            if not self.request.user.is_authenticated:
                raise PermissionDenied("No puedes editar este evento.")
            super().perform_update(serializer)
        except PermissionDenied:
            raise
        except Exception as e:
            logger.error(f"Error updating event: {e}")
            raise ValidationError("Error inesperado al actualizar el evento")

    def perform_destroy(self, instance):
        try:
            if not self.request.user.is_authenticated:
                raise PermissionDenied("No puedes eliminar este evento.")
            super().perform_destroy(instance)
        except DatabaseError as e:
            logger.error(f"Database error deleting event: {e}")
            raise ValidationError("Error de base de datos al eliminar el evento")
        except Exception as e:
            logger.error(f"Error deleting event: {e}")
            raise ValidationError("Error inesperado al eliminar el evento")


# Song Likes View
class SongLikesView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(description="Obtener el conteo de likes de una canción")
    def get(self, request, song_id):
        try:
            song = get_object_or_404(Song, id=song_id)
            likes_count = cache.get(f"song_{song_id}_likes_count", song.likes_count)
            return Response({
                "song_id": song_id,
                "likes_count": likes_count,
                "title": song.title
            })
        except Exception as e:
            logger.error(f"Error getting song likes: {e}")
            return Response(
                {"error": "Error al obtener los likes de la canción"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Song List View with Flexible Search
@extend_schema(
    description="Lista y busca canciones con filtros avanzados",
    parameters=[
        OpenApiParameter(name='title', description='Filtrar por título', required=False, type=str),
        OpenApiParameter(name='artist', description='Filtrar por artista', required=False, type=str),
        OpenApiParameter(name='genre', description='Filtrar por género', required=False, type=str),
    ]
)



class UploadThrottle(UserRateThrottle):
    scope = 'upload'  # Usará la tasa definida en settings.py
    
    http_method_names = ['post', 'put', 'patch']
    
    @classmethod
    def get_schema_operation_parameters(cls):
        return []

class SongListView(generics.ListCreateAPIView):
    serializer_class = SongSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['genre', 'artist']
    search_fields = ['title', 'artist', 'genre']
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [UploadThrottle]
    
    # Cambiamos el queryset inicial para que no esté vacío
    queryset = Song.objects.all()

    def get_queryset(self):
        # Construimos la clave de caché basada en todos los parámetros de búsqueda
        cache_key = f"songs_list_{self.request.query_params.urlencode()}"
        queryset = cache.get(cache_key)
        
        if queryset is None:
            # Base queryset con todas las anotaciones necesarias
            queryset = Song.objects.annotate(
                likes_count_dynamic=Count('like', distinct=True),
                comments_count=Count('comments', distinct=True),
                downloads_count=Count('download', distinct=True)
            ).select_related('uploaded_by').prefetch_related(
                Prefetch(
                    'comments',
                    queryset=Comment.objects.order_by('-created_at'),
                    to_attr='prefetched_comments'
                )
            )
            
            # Aplicamos filtros adicionales
            if self.request.query_params.get('my_songs', '').lower() == 'true':
                if not self.request.user.is_authenticated:
                    raise PermissionDenied("Debes iniciar sesión para ver tus canciones")
                queryset = queryset.filter(uploaded_by=self.request.user)
            
            # Aplicamos búsqueda por título si está presente
            title_query = self.request.query_params.get('title')
            if title_query:
                queryset = queryset.filter(title__icontains=title_query)
            
            # Guardamos en caché solo después de aplicar todos los filtros
            cache.set(cache_key, queryset, 300)
        
        return queryset

    # ... (el resto de los métodos permanecen igual)

class MySongsView(generics.ListAPIView):
    """
    Vista para listar las canciones del usuario actual con estadísticas.
    """
    serializer_class = SongSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [SearchFilter]
    search_fields = ['title', 'genre', 'artist']

    def get_queryset(self):
        user = self.request.user
        cache_key = f"user_{user.id}_songs"
        queryset = cache.get(cache_key)
        
        if queryset is None:
            queryset = Song.objects.filter(
                uploaded_by=user
            ).annotate(
                total_likes=Count('like', distinct=True),  # Anotación renombrada
                total_comments=Count('comments', distinct=True),  # Anotación renombrada
                total_downloads=Count('download', distinct=True),  # Anotación renombrada
                last_download=Max('download__downloaded_at')
            ).select_related('uploaded_by').order_by('-created_at')
            
            cache.set(cache_key, queryset, 120)  # Cache por 2 minutos
        
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        # Obtener estadísticas directamente del queryset
        stats = {
            'total_songs': queryset.count(),
            'total_downloads': queryset.aggregate(
                Sum('total_downloads')
            )['total_downloads__sum'] or 0,
            'total_likes': queryset.aggregate(
                Sum('total_likes')
            )['total_likes__sum'] or 0,
            'last_upload': queryset.first().created_at if queryset.exists() else None
        }

        # Serializar los resultados
        serializer = self.get_serializer(queryset, many=True)
        
        return Response({
            'stats': stats,
            'songs': serializer.data
        })
class SongSearchSuggestionsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        try:
            query = self.request.query_params.get('query', '').strip()[:100]
            if not query:
                return Response({"suggestions": []})

            songs = Song.objects.filter(
                Q(title__icontains=query) | Q(artist__icontains=query)
            ).values('title', 'artist', 'genre')[:5]

            return Response({"suggestions": list(songs)})
        except DatabaseError as e:
            logger.error(f"Database error in suggestions: {e}")
            return Response(
                {"error": "Error al obtener sugerencias"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.error(f"Error in suggestions: {e}")
            return Response(
                {"error": "Error inesperado al obtener sugerencias"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Like Song View
@extend_schema(description="Dar o quitar like a una canción")
class LikeSongView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, song_id):
        try:
            song = get_object_or_404(Song, id=song_id)
            like, created = Like.objects.get_or_create(user=request.user, song=song)
            
            if not created:
                like.delete()
                message = "Like removido"
            else:
                message = "Like agregado"

            # Actualización atómica del contador
            song.likes_count = Like.objects.filter(song=song).count()
            song.save(update_fields=['likes_count'])
            cache.set(f"song_{song_id}_likes_count", song.likes_count, timeout=300)

            return Response({
                "message": message,
                "likes_count": song.likes_count,
                "song_id": song_id
            })
        except DatabaseError as e:
            logger.error(f"Database error in like: {e}")
            return Response(
                {"error": "Error de base de datos al procesar el like"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.error(f"Error in like: {e}")
            return Response(
                {"error": "Error inesperado al procesar el like"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Download Song View
@extend_schema(description="Descargar una canción con control de frecuencia")


class DownloadSongView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    # Configuración de límites (1 hora de cooldown)
    DOWNLOAD_COOLDOWN = timedelta(hours=1)  # Tiempo de espera entre descargas de la misma canción

    def get(self, request, song_id):
        # Claves para el sistema de bloqueo y control
        lock_key = f"download_lock_{request.user.id}_{song_id}"
        download_cooldown_key = f"download_cooldown_{request.user.id}_{song_id}"

        try:
            song = get_object_or_404(Song, id=song_id)

            if not song.file or not song.file.storage.exists(song.file.name):
                raise NotFound("El archivo de la canción no está disponible")

            # Verificar si el usuario está intentando descargar actualmente
            if cache.get(lock_key):
                return Response(
                    {"error": "Estás en proceso de descarga de esta canción. Por favor espera."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS
                )

            # Bloquear para evitar descargas simultáneas
            cache.set(lock_key, True, timeout=60)

            with transaction.atomic():
                # Verificar si ya descargó esta canción recientemente (en la última hora)
                last_download = Download.objects.filter(
                    user=request.user,
                    song=song,
                    downloaded_at__gte=timezone.now() - self.DOWNLOAD_COOLDOWN
                ).order_by('-downloaded_at').first()

                if last_download and not request.user.is_staff:
                    cache.delete(lock_key)
                    remaining_time = (last_download.downloaded_at + self.DOWNLOAD_COOLDOWN) - timezone.now()
                    return Response(
                        {
                            "error": f"Ya descargaste esta canción recientemente. Por favor espera {remaining_time}",
                            "cooldown_remaining": str(remaining_time),
                            "last_download_time": last_download.downloaded_at.isoformat()
                        },
                        status=status.HTTP_429_TOO_MANY_REQUESTS
                    )

                # Registrar la descarga
                Download.objects.create(user=request.user, song=song)
                
                # Marcar esta canción como descargada recientemente (en caché y DB)
                cache.set(download_cooldown_key, True, timeout=self.DOWNLOAD_COOLDOWN.total_seconds())
                
                # Liberar el bloqueo
                cache.delete(lock_key)

            # Preparar la respuesta con el archivo
            file = song.file.open('rb')
            filename = f"{slugify(song.title)}-{slugify(song.artist)}{os.path.splitext(song.file.name)[1]}"
            response = FileResponse(file, as_attachment=True, filename=filename)
            response["Content-Length"] = song.file.size
            
            # Headers adicionales para información del usuario
            response["X-Download-Cooldown"] = self.DOWNLOAD_COOLDOWN.total_seconds()
            response["X-Download-Time"] = timezone.now().isoformat()
            
            return response

        except Exception as e:
            # Asegurarse de liberar el bloqueo en caso de error
            cache.delete(lock_key)
            logger.error(f"Error en descarga: {str(e)}", exc_info=True)
            return Response(
                {"error": "No se pudo completar la descarga"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
import random

# Stream Song View
@extend_schema(description="Reproducir una canción en streaming")
class StreamSongView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, song_id):
        try:
            song = get_object_or_404(Song, id=song_id)
            if not song.file:
                raise NotFound("Archivo no disponible")

            def generate_stream():
                try:
                    with default_storage.open(song.file.name, 'rb') as f:
                        while chunk := f.read(8192):
                            yield chunk
                except IOError as e:
                    logger.error(f"Streaming error: {e}")
                    raise NotFound("Error al acceder al archivo") from e

            response = StreamingHttpResponse(generate_stream(), content_type="audio/mpeg")
            response['Accept-Ranges'] = 'bytes'
            response['Content-Length'] = song.file.size
            return response
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            return Response(
                {"error": "Error al iniciar la transmisión"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Comments Views
@extend_schema(tags=['Comentarios'])
class CommentListCreateView(generics.ListCreateAPIView):
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = CommentPagination

    def get_queryset(self):
        try:
            return Comment.objects.filter(song_id=self.kwargs['song_id']).select_related('user').order_by("-created_at")
        except Exception as e:
            logger.error(f"Error getting comments: {e}")
            raise ValidationError("Error al obtener comentarios")

    def perform_create(self, serializer):
        try:
            serializer.save(user=self.request.user, song_id=self.kwargs['song_id'])
            cache.delete(f"song_{self.kwargs['song_id']}_comments")
        except IntegrityError as e:
            logger.error(f"Error creating comment: {e}")
            raise ValidationError("Error de integridad al crear comentario")
        except Exception as e:
            logger.error(f"Error creating comment: {e}")
            raise ValidationError("Error inesperado al crear comentario")


@extend_schema(tags=['Comentarios'])
class SongCommentsDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def handle_exception(self, exc):
        if isinstance(exc, DatabaseError):
            logger.error(f"Database error in comment detail: {exc}")
            return Response(
                {"error": "Error de base de datos al procesar comentario"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        return super().handle_exception(exc)

    def perform_update(self, serializer):
        try:
            if serializer.instance.user != self.request.user:
                raise PermissionDenied("No puedes editar este comentario")
            super().perform_update(serializer)
        except DatabaseError as e:
            logger.error(f"Database error updating comment: {e}")
            raise ValidationError("Error al actualizar el comentario")

    def perform_destroy(self, instance):
        try:
            if instance.user != self.request.user:
                raise PermissionDenied("No puedes eliminar este comentario")
            super().perform_destroy(instance)
            cache.delete(f"song_{instance.song_id}_comments")
        except DatabaseError as e:
            logger.error(f"Database error deleting comment: {e}")
            raise ValidationError("Error al eliminar el comentario")


# Artist List View
@extend_schema(description="Lista de artistas únicos con cache")
class ArtistListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        try:
            artists = cache.get_or_set(
                "unique_artists_list",
                lambda: list(Song.objects.values_list("artist", flat=True).distinct()),
                600
            )
            return Response({"artists": artists})
        except DatabaseError as e:
            logger.error(f"Database error getting artists: {e}")
            return Response(
                {"error": "Error al obtener la lista de artistas"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.error(f"Error getting artists: {e}")
            return Response(
                {"error": "Error inesperado al obtener artistas"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# Random Songs View
# Vista para artistas destacados
@extend_schema(description="Obtener artistas destacados para el carrusel")
class FeaturedArtistsView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        try:
            # Obtener artistas únicos con sus imágenes y estadísticas
            featured_artists = Song.objects.exclude(
                Q(image__isnull=True) | Q(image='')
            ).values('artist').annotate(
                song_count=Count('id'),
                total_likes=Sum('likes_count'),
                latest_image=Max('image'),
                latest_genre=Max('genre')
            ).order_by('-total_likes')[:8]  # Limitar a 8 artistas más populares
            
            # Construir la respuesta
            artists_data = []
            for artist in featured_artists:
                # Obtener la canción más reciente del artista para la bio
                latest_song = Song.objects.filter(
                    artist=artist['artist']
                ).exclude(
                    Q(image__isnull=True) | Q(image='')
                ).order_by('-created_at').first()
                
                artists_data.append({
                    'name': artist['artist'],
                    'genre': artist['latest_genre'],
                    'song_count': artist['song_count'],
                    'total_likes': artist['total_likes'],
                    'image_url': latest_song.image.url if latest_song and latest_song.image else None,
                    'bio': f"Artista con {artist['song_count']} canción(es) y {artist['total_likes']} likes en total."
                })
            
            return Response({"artists": artists_data})
            
        except Exception as e:
            logger.error(f"Error getting featured artists: {e}")
            return Response(
                {"error": "Error al obtener artistas destacados"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
@extend_schema(description="Selección aleatoria de canciones")
class RandomSongsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            num_songs = 6
            all_songs = Song.objects.all()

            if not all_songs.exists():
                return Response(
                    {"error": "No hay canciones disponibles en este momento."},
                    status=status.HTTP_404_NOT_FOUND
                )

            random_songs = random.sample(list(all_songs), min(num_songs, all_songs.count()))
            serializer = SongSerializer(random_songs, many=True)

            return Response({"random_songs": serializer.data}, status=status.HTTP_200_OK)
        except ValueError as e:
            logger.error(f"Value error in random songs: {e}")
            return Response(
                {"error": "Error en la selección de canciones"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.error(f"Error in random songs: {e}")
            return Response(
                {"error": "Error al obtener canciones aleatorias"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
 
 