from rest_framework.permissions import BasePermission

class IsOwnerOrAdmin(BasePermission):
    def has_object_permission(self, request, view, obj):
        return bool(
            request.user.is_staff or
            (hasattr(obj, 'usuario') and obj.usuario == request.user) or
            (hasattr(obj, 'user') and obj.user == request.user)
        )

class IsDeviceOwnerOrAdmin(BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.user.is_staff or obj.usuario == request.user

class IsAdminOrAgenciaManager(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_staff or request.user.groups.filter(name='Agencia Managers').exists()

class IsAdminOrAgenciaAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_staff or request.user.groups.filter(name='Agencia Admins').exists()

class IsTransferOwnerOrAdmin(BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.user.is_staff or obj.emisor == request.user

class IsTransactionOwnerOrAdmin(BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.user.is_staff or obj.monedero_usuario.usuario == request.user

class IsAgenteOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_staff or getattr(request.user, 'es_agente', False)
        )

class IsTransferenciaParticipant(BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.user == getattr(obj, 'emisor', None) or request.user == getattr(obj, 'receptor', None)
