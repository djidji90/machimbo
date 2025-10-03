# monedero/filters.py
import django_filters
from .models import (
    IntentoFallido,
    Agencia,
    Agente,
    DispositivoSeguro,
    Transaccion,
    TransaccionRetenida,
    Transferencia,
    AuditoriaMonedero, 
    Notificacion,
    PoliticaComisiones
)

class IntentoFallidoFilter(django_filters.FilterSet):
    fecha_min = django_filters.DateFilter(field_name='fecha', lookup_expr='gte')
    fecha_max = django_filters.DateFilter(field_name='fecha', lookup_expr='lte')

    class Meta:
        model = IntentoFallido
        fields = ['usuario', 'ip', 'accion', 'dispositivo']

class AgenciaFilter(django_filters.FilterSet):
    class Meta:
        model = Agencia
        fields = {
            'nombre': ['exact', 'icontains'],
            'ciudad': ['exact', 'icontains'],
            'activa': ['exact']
        }

class AgenteFilter(django_filters.FilterSet):
    class Meta:
        model = Agente
        fields = {
            'usuario__username': ['exact', 'icontains'],
            'agencia__nombre': ['exact', 'icontains'],
            'activo': ['exact']
        }

class DispositivoFilter(django_filters.FilterSet):
    class Meta:
        model = DispositivoSeguro
        fields = {
            'nombre': ['exact', 'icontains'],
            'activo': ['exact'],
            'fecha_registro': ['gte', 'lte']
        }

class TransaccionFilter(django_filters.FilterSet):
    fecha_min = django_filters.DateFilter(field_name='fecha_creacion', lookup_expr='gte')
    fecha_max = django_filters.DateFilter(field_name='fecha_creacion', lookup_expr='lte')
    monto_min = django_filters.NumberFilter(field_name='monto', lookup_expr='gte')
    monto_max = django_filters.NumberFilter(field_name='monto', lookup_expr='lte')

    class Meta:
        model = Transaccion
        fields = ['tipo', 'estado', 'monedero']

class TransaccionRetenidaFilter(django_filters.FilterSet):
    class Meta:
        model = TransaccionRetenida
        fields = ['estado', 'monedero_usuario', 'monedero_proveedor']

class TransferenciaFilter(django_filters.FilterSet):
    fecha_min = django_filters.DateFilter(field_name='fecha', lookup_expr='gte')
    fecha_max = django_filters.DateFilter(field_name='fecha', lookup_expr='lte')

    class Meta:
        model = Transferencia
        fields = ['estado', 'emisor', 'receptor']

class AuditoriaFilter(django_filters.FilterSet):
    fecha_min = django_filters.DateFilter(field_name='fecha', lookup_expr='gte')
    fecha_max = django_filters.DateFilter(field_name='fecha', lookup_expr='lte')

    class Meta:
        model = AuditoriaMonedero
        fields = ['accion']
class NotificacionFilter(django_filters.FilterSet):
    fecha_min = django_filters.DateFilter(field_name='fecha', lookup_expr='gte')
    fecha_max = django_filters.DateFilter(field_name='fecha', lookup_expr='lte')
    
    class Meta:
        model = Notificacion
        fields = ['tipo', 'leida']

class PoliticaComisionesFilter(django_filters.FilterSet):
    class Meta:
        model = PoliticaComisiones
        fields = {
            'nombre': ['exact', 'icontains'],
            'activa': ['exact'],
            'fecha_creacion': ['gte', 'lte']
        }
