from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ConfiguracionSistemaViewSet,
    AgenciaViewSet,
    AgenteViewSet,
    MonederoViewSet,
    TransferenciaViewSet,
    RecargaViewSet,
    AuditoriaTransferenciaViewSet,
    AuditoriaRecargaViewSet,
    AuditoriaMonederoViewSet,
    AuditoriaAgenteViewSet,
    DashboardAdminViewSet,
    ReporteViewSet,
    NotificacionViewSet,
    TransaccionViewSet,
    OperacionesViewSet,
)
from monedero import views

router = DefaultRouter()
router.register(r'configuracion', ConfiguracionSistemaViewSet, basename='configuracion')
router.register(r'agencias', AgenciaViewSet, basename='agencias')
# Cambia en tus rutas API
router.register(r'agentes', AgenteViewSet, basename='agente')  # Cambia el prefijo
router.register(r'monedero', MonederoViewSet, basename='monedero')
router.register(r'transferencias', TransferenciaViewSet, basename='transferencias')
router.register(r'recargas', RecargaViewSet, basename='recargas')
router.register(r'auditoria-transferencias', AuditoriaTransferenciaViewSet, basename='auditoria-transferencias')
router.register(r'auditoria-recargas', AuditoriaRecargaViewSet, basename='auditoria-recargas')
router.register(r'auditoria-monedero', AuditoriaMonederoViewSet, basename='auditoria-monedero')
router.register(r'auditoria-agente', AuditoriaAgenteViewSet, basename='auditoria-agente')
router.register(r'dashboard', DashboardAdminViewSet, basename='dashboard')
router.register(r'reportes', ReporteViewSet, basename='reportes')
router.register(r'notificaciones', NotificacionViewSet, basename='notificaciones')
router.register(r'transacciones', TransaccionViewSet, basename='transacciones')

# Operaciones es un ViewSet sin queryset, se registra con basename y sin prefix para acciones personalizadas
from rest_framework.urlpatterns import format_suffix_patterns
from rest_framework.routers import SimpleRouter

operaciones_list = OperacionesViewSet.as_view({
    'post': 'validar_pin',
})

urlpatterns = [
    path('api/', include(router.urls)),
    path('api/operaciones/validar_pin/', operaciones_list, name='validar_pin'),
    path('monedero/api/', include(router.urls)),
     path('agencias/<int:pk>/dashboard/', views.agencia_dashboard, name='agencia_dashboard'),
]
