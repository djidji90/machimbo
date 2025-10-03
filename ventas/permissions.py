from rest_framework.permissions import BasePermission, IsAuthenticated, IsAdminUser

class IsAgenteOrAdmin(BasePermission):
    """
    Permite acceso solo a usuarios con rol de agente o administradores
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and
            (request.user.is_staff or 
             getattr(request.user, 'es_agente', False))
)

