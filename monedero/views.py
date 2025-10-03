import json
import logging
from multiprocessing import Value
from django.forms import FloatField
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.db.models import Q, F
from decimal import Decimal
from django.db.models import Sum
from django.db.models.functions import Cast
from django.db.models import FloatField, IntegerField, CharField
from django.core.exceptions import SuspiciousOperation
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Func

from rest_framework.pagination import PageNumberPagination
from .models import (
    ConfiguracionSistema,
    Agencia,
    Agente,
    Monedero,
    Transferencia,
    Recarga,
    AuditoriaTransferencia,
    AuditoriaRecarga,
    AuditoriaMonedero,
    AuditoriaAgente,
    DashboardAdmin,
    Reporte,
    Notificacion,
    Transaccion
)
from .serializers import (
    ConfiguracionSistemaSerializer,
    AgenciaSerializer,
    AgenteSerializer,
    MonederoSerializer,
    TransferenciaSerializer,
    RecargaSerializer,
    AuditoriaTransferenciaSerializer,
    AuditoriaRecargaSerializer,
    AuditoriaMonederoSerializer,
    AuditoriaAgenteSerializer,
    DashboardAdminSerializer,
    ReporteSerializer,
    NotificacionSerializer,
    TransaccionSerializer,
    TransferenciaCreateSerializer,
    RecargaCreateSerializer,
    PinOperacionesSerializer,
    CodigoVerificacionSerializer
)
from .permissions import (
    IsAdminOrAgenciaAdmin,
    IsAgenteOrAdmin,
    IsOwnerOrAdmin,
    IsTransferenciaParticipant
)
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()

## ----------------------------
## 1. VISTAS DE CONFIGURACIÓN
## ----------------------------

class ConfiguracionSistemaViewSet(viewsets.ModelViewSet):
    queryset = ConfiguracionSistema.objects.all()
    serializer_class = ConfiguracionSistemaSerializer
    permission_classes = [IsAdminUser]
    http_method_names = ['get', 'put', 'patch', 'head', 'options']

    def get_object(self):
        return ConfiguracionSistema.cargar()

    def list(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

## ----------------------------
## 2. VISTAS DE AGENCIAS Y AGENTES
## ----------------------------

class AgenciaViewSet(viewsets.ModelViewSet):
    queryset = Agencia.objects.all()
    serializer_class = AgenciaSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['activa', 'ciudad']
    search_fields = ['codigo', 'nombre', 'ciudad']
    ordering_fields = ['nombre', 'fecha_registro']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['get'])
    def agentes(self, request, pk=None):
        agencia = self.get_object()
        agentes = agencia.agentes_asociados.filter(activo=True)
        page = self.paginate_queryset(agentes)
        if page is not None:
            serializer = AgenteSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = AgenteSerializer(agentes, many=True)
        return Response(serializer.data)

from rest_framework import viewsets, status
from rest_framework.response import Response




class AgenteViewSet(viewsets.ModelViewSet):
    queryset = Agente.objects.select_related('usuario', 'agencia').all()
    serializer_class = AgenteSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['activo', 'agencia', 'agencia__ciudad']
    search_fields = ['codigo_agente', 'usuario__username', 'usuario__first_name', 'usuario__last_name']
    ordering_fields = ['fecha_registro', 'comision_acumulada', 'codigo_agente']
    ordering = ['-fecha_registro']

    def get_permissions(self):
        if self.action in ['create', 'destroy', 'update', 'partial_update']:
            return [IsAdminOrAgenciaAdmin()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        """Asigna campos adicionales al crear un agente"""
        serializer.save(
            usuario=self.request.user if self.request.user.is_authenticated else None,
            agencia=self.request.user.agencia if hasattr(self.request.user, 'agencia') else None
        )

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Endpoint para obtener información del agente actual"""
        if not request.user.is_authenticated:
            return Response(
                {'detail': 'Autenticación requerida'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        try:
            agente = self.get_queryset().get(usuario=request.user)
            serializer = self.get_serializer(agente)
            return Response(serializer.data)
        except Agente.DoesNotExist:
            logger.warning(f'Usuario {request.user.id} intentó acceder a endpoint de agente sin serlo')
            return Response(
                {'detail': 'No tienes permisos de agente'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        except Exception as e:
            logger.error(f'Error en endpoint /agentes/me: {str(e)}')
            return Response(
                {'detail': 'Error interno del servidor'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class SafeJsonbExtractor(Func):
    """
    Función segura para extraer valores numéricos de campos JSONB
    """
    function = 'jsonb_extract_path_text'
    template = "CAST(%(function)s(%(expressions)s::jsonb, '%(key)s') AS numeric)"
    output_field = FloatField()

    def __init__(self, expression, key, **extra):
        if not isinstance(key, str):
            raise SuspiciousOperation("Key must be a string")
        super().__init__(expression, key=key, **extra)

class MonederoPagination(PageNumberPagination):
    """
    Paginación personalizada con ordenamiento por defecto
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def paginate_queryset(self, queryset, request, view=None):
        # Asegurar ordenamiento consistente
        if not queryset.ordered:
            queryset = queryset.order_by('-id')
        return super().paginate_queryset(queryset, request, view)

class MonederoViewSet(viewsets.ModelViewSet):
    """
    ViewSet optimizado para manejar monederos con:
    - Paginación segura
    - Procesamiento JSONB robusto
    - Manejo de errores mejorado
    """
    queryset = Monedero.objects.select_related('usuario').order_by('-id')
    serializer_class = MonederoSerializer
    pagination_class = MonederoPagination
    http_method_names = ['get', 'head', 'options']

    def get_queryset(self):
        """
        Queryset con anotaciones seguras para campos JSONB
        """
        queryset = super().get_queryset()
        
        if self.request.user.is_staff:
            try:
                queryset = queryset.annotate(
                    saldo_actual=SafeJsonbExtractor('auditorias__estado_posterior', 'saldo')
                )
            except Exception as e:
                logger.error(f"Error en annotate: {str(e)}")
                queryset = queryset.annotate(
                    saldo_actual=Value(0.0, output_field=FloatField())
                )
        return queryset

    @action(detail=False, methods=['get'])
    def mi_monedero(self, request):
        """
        Endpoint seguro para obtener el monedero del usuario actual
        """
        try:
            monedero = Monedero.objects.get(usuario=request.user)
            serializer = self.get_serializer(monedero)
            return Response(serializer.data)
        except Monedero.DoesNotExist:
            logger.error(f"Monedero no encontrado para {request.user}")
            return Response(
                {'error': 'Monedero no encontrado'}, 
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['get'], permission_classes=[IsAdminUser])
    def estadisticas(self, request, pk=None):
        """
        Endpoint para estadísticas con procesamiento en Python
        """
        monedero = self.get_object()
        
        try:
            registros = list(AuditoriaMonedero.objects.filter(
                monedero=monedero,
                estado_posterior__has_key='saldo'
            ).order_by('fecha').values('fecha', 'estado_posterior'))
            
            saldos = []
            for reg in registros:
                try:
                    estado = reg['estado_posterior']
                    if isinstance(estado, str):
                        estado = json.loads(estado)
                    saldo = float(estado.get('saldo', 0))
                    saldos.append({
                        'fecha': reg['fecha'].isoformat(),
                        'saldo': saldo
                    })
                except (ValueError, TypeError, KeyError, json.JSONDecodeError) as e:
                    logger.warning(f"Registro con saldo inválido: {e}")
                    continue
            
            if not saldos:
                return Response({
                    'monedero_id': monedero.id,
                    'mensaje': 'No hay datos suficientes'
                }, status=status.HTTP_404_NOT_FOUND)
            
            valores = [item['saldo'] for item in saldos]
            response_data = {
                'monedero_id': monedero.id,
                'saldo_maximo': max(valores),
                'saldo_minimo': min(valores),
                'saldo_promedio': sum(valores) / len(valores),
                'total_registros': len(valores),
                'historico': saldos[-100:]  # Últimos 100 registros
            }
            
            return Response(response_data)
        
        except Exception as e:
            logger.error(f"Error en estadisticas: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Error al procesar estadísticas'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            
            )
class TransferenciaViewSet(viewsets.ModelViewSet):
    queryset = Transferencia.objects.select_related('emisor', 'receptor')
    serializer_class = TransferenciaSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['estado', 'emisor', 'receptor']
    ordering_fields = ['fecha_creacion', 'cantidad']
    http_method_names = ['get', 'post', 'head', 'options']

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated()]
        elif self.action in ['retrieve', 'list']:
            return [IsTransferenciaParticipant()]
        return [IsAdminUser()]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return self.queryset.none()
        return self.queryset.filter(Q(emisor=user) | Q(receptor=user))

    def create(self, request, *args, **kwargs):
        serializer = TransferenciaCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        try:
            transferencia = serializer.save()
            logger.info(
                f"Transferencia creada: {transferencia.referencia}",
                extra={'user': request.user.id}
            )
            return Response(
                TransferenciaSerializer(transferencia).data,
                status=status.HTTP_201_CREATED,
                headers=self.get_success_headers(serializer.data)
            )
        except ValidationError as e:
            logger.warning(
                f"Error de validación en transferencia: {str(e)}",
                extra={'user': request.user.id}
            )
            raise
        except Exception as e:
            logger.error(
                f"Error al crear transferencia: {str(e)}",
                exc_info=True,
                extra={'user': request.user.id}
            )
            return Response(
                {'error': 'Ocurrió un error al procesar la transferencia'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def verificar(self, request, pk=None):
        transferencia = self.get_object()
        serializer = CodigoVerificacionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            if transferencia.verificar(serializer.validated_data['codigo']):
                logger.info(
                    f"Transferencia {transferencia.referencia} verificada",
                    extra={'user': request.user.id}
                )
                return Response({'status': 'Transferencia verificada'})
            
            logger.warning(
                f"Código inválido para transferencia {transferencia.referencia}",
                extra={'user': request.user.id}
            )
            return Response(
                {'error': 'Código inválido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(
                f"Error al verificar transferencia: {str(e)}",
                exc_info=True,
                extra={'user': request.user.id}
            )
            return Response(
                {'error': 'Error en verificación'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class RecargaViewSet(viewsets.ModelViewSet):
    queryset = Recarga.objects.select_related('usuario', 'agente')
    serializer_class = RecargaSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['estado', 'usuario', 'agente', 'metodo_pago']
    ordering_fields = ['fecha_creacion', 'monto']
    http_method_names = ['get', 'post', 'head', 'options']

    def get_permissions(self):
        if self.action == 'create':
            return [IsAgenteOrAdmin()]
        elif self.action in ['retrieve', 'list']:
            return [IsOwnerOrAdmin()]
        return [IsAdminUser()]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return self.queryset.none()
        
        if user.is_staff:
            return self.queryset.all()
        
        try:
            agente = Agente.objects.get(usuario=user)
            return self.queryset.filter(Q(usuario=user) | Q(agente=agente))
        except Agente.DoesNotExist:
            return self.queryset.filter(usuario=user)

    def create(self, request, *args, **kwargs):
        serializer = RecargaCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        try:
            recarga = serializer.save()
            logger.info(
                f"Recarga creada: {recarga.referencia}",
                extra={'user': request.user.id}
            )
            return Response(
                RecargaSerializer(recarga).data,
                status=status.HTTP_201_CREATED,
                headers=self.get_success_headers(serializer.data)
            )
        except ValidationError as e:
            logger.warning(
                f"Error de validación en recarga: {str(e)}",
                extra={'user': request.user.id}
            )
            raise
        except Exception as e:
            logger.error(
                f"Error al crear recarga: {str(e)}",
                exc_info=True,
                extra={'user': request.user.id}
            )
            return Response(
                {'error': 'Ocurrió un error al procesar la recarga'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

## ----------------------------
## 5. VISTAS DE AUDITORÍA
## ----------------------------

class AuditoriaBaseViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ['fecha']
    
    def get_queryset(self):
        return super().get_queryset().select_related('usuario')

class AuditoriaTransferenciaViewSet(AuditoriaBaseViewSet):
    queryset = AuditoriaTransferencia.objects.all()
    serializer_class = AuditoriaTransferenciaSerializer
    filterset_fields = ['accion', 'transferencia', 'transferencia__emisor', 'transferencia__receptor']


class AuditoriaRecargaViewSet(AuditoriaBaseViewSet):
    queryset = AuditoriaRecarga.objects.all()
    serializer_class = AuditoriaRecargaSerializer
    filterset_fields = ['accion', 'usuario', 'recarga']

class AuditoriaMonederoViewSet(AuditoriaBaseViewSet):
    queryset = AuditoriaMonedero.objects.all()
    serializer_class = AuditoriaMonederoSerializer
    filterset_fields = ['accion', 'usuario', 'monedero']

class AuditoriaAgenteViewSet(AuditoriaBaseViewSet):
    queryset = AuditoriaAgente.objects.all()
    serializer_class = AuditoriaAgenteSerializer
    filterset_fields = ['accion', 'usuario', 'agente']

## ----------------------------
## 6. VISTAS DE DASHBOARD Y REPORTES
## ----------------------------

class DashboardAdminViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DashboardAdmin.objects.all()
    serializer_class = DashboardAdminSerializer
    permission_classes = [IsAdminUser]
    http_method_names = ['get', 'head', 'options']

    def list(self, request, *args, **kwargs):
        try:
            dashboard = DashboardAdmin.obtener_actual()
            serializer = self.get_serializer(dashboard)
            return Response(serializer.data)
        except Exception as e:
            logger.error(
                f"Error al obtener dashboard: {str(e)}",
                exc_info=True,
                extra={'user': request.user.id if request.user.is_authenticated else None}
            )
            return Response(
                {'error': 'Error al cargar el dashboard'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ReporteViewSet(viewsets.ModelViewSet):
    queryset = Reporte.objects.select_related('creado_por')
    serializer_class = ReporteSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['tipo', 'estado', 'creado_por']
    ordering_fields = ['fecha_creacion', 'fecha_completado']

    def get_permissions(self):
        if self.action in ['create', 'retrieve', 'list']:
            return [IsAuthenticated()]
        return [IsAdminUser()]

    def perform_create(self, serializer):
        serializer.save(creado_por=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def generar(self, request, pk=None):
        reporte = self.get_object()
        try:
            reporte.generar()
            logger.info(
                f"Reporte {reporte.id} generado",
                extra={'user': request.user.id}
            )
            return Response({'status': 'Reporte generado'})
        except Exception as e:
            logger.error(
                f"Error al generar reporte {reporte.id}: {str(e)}",
                exc_info=True,
                extra={'user': request.user.id}
            )
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

## ----------------------------
## 7. VISTAS DE NOTIFICACIONES
## ----------------------------

class NotificacionViewSet(viewsets.ModelViewSet):
    serializer_class = NotificacionSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['tipo', 'leida']
    ordering_fields = ['fecha']
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            return Notificacion.objects.filter(usuario=user)
        return Notificacion.objects.none()

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'partial_update']:
            return [IsAuthenticated()]
        return [IsAdminUser()]

    @action(detail=False, methods=['get'])
    def no_leidas(self, request):
        notificaciones = self.get_queryset().filter(leida=False)
        page = self.paginate_queryset(notificaciones)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = self.get_serializer(notificaciones, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def marcar_leida(self, request, pk=None):
        notificacion = self.get_object()
        try:
            notificacion.leida = True
            notificacion.save()
            logger.info(
                f"Notificación {notificacion.id} marcada como leída",
                extra={'user': request.user.id}
            )
            return Response({'status': 'Notificación marcada como leída'})
        except Exception as e:
            logger.error(
                f"Error al marcar notificación como leída: {str(e)}",
                exc_info=True,
                extra={'user': request.user.id}
            )
            return Response(
                {'error': 'Error al actualizar notificación'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

## ----------------------------
## 8. VISTAS DE TRANSACCIONES
## ----------------------------

class TransaccionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TransaccionSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['tipo', 'estado', 'usuario']
    ordering_fields = ['creado_en', 'cantidad']

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Transaccion.objects.none()
        
        if user.is_staff:
            return Transaccion.objects.all()
        return Transaccion.objects.filter(usuario=user)

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsAdminUser()]

## ----------------------------
## VISTAS ADICIONALES PARA OPERACIONES ESPECÍFICAS
## ----------------------------

class OperacionesViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def validar_pin(self, request):
        serializer = PinOperacionesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            agente = Agente.objects.get(usuario=request.user)
            if agente.verificar_pin_operaciones(serializer.validated_data['pin']):
                logger.info(
                    "PIN validado correctamente",
                    extra={'user': request.user.id}
                )
                return Response({'status': 'PIN válido'})
                
            logger.warning(
                "PIN incorrecto",
                extra={'user': request.user.id}
            )
            return Response(
                {'error': 'PIN incorrecto'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Agente.DoesNotExist:
            logger.warning(
                "Intento de validar PIN por usuario no agente",
                extra={'user': request.user.id}
            )
            return Response(
                {'error': 'Usuario no es un agente'},
                status=status.HTTP_403_FORBIDDEN
            )
        except Exception as e:
            logger.error(
                f"Error al validar PIN: {str(e)}",
                exc_info=True,
                extra={'user': request.user.id}
            )
            return Response(
                {'error': 'Error al validar PIN'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
# monedero/views.py
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(['GET'])
def agencia_dashboard(request, pk):
    agencia = get_object_or_404(Agencia, pk=pk)
    data = {
        'agencia_id': agencia.id,
        'nombre': agencia.nombre,
        'estadisticas': {
            'agentes_activos': agencia.agentes_activos().count(),
            'total_recargas': Recarga.objects.filter(agente__agencia=agencia).count(),
            'saldo_total': Monedero.objects.filter(
                usuario__agente__agencia=agencia
            ).aggregate(Sum('saldo'))['saldo__sum'] or 0
        }
    }
    return Response(data)