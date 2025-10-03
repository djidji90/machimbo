from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView
from .views import (
    RegisterView,
    ProtectedView,
    RegisterUserVisit,
    CustomTokenObtainPairView,
)

app_name = "users"  # Namespacing ordenado en el proyecto

urlpatterns = [
    # Registro y autenticación
    path("register/", RegisterView.as_view(), name="register"),  # Registro de usuarios
    path("login/", CustomTokenObtainPairView.as_view(), name="login"),  # Login (token JWT)
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),  # Refrescar token
    path("token/verify/", TokenVerifyView.as_view(), name="token_verify"),  # Verificar token

    # Seguridad / prueba
    path("protected/", ProtectedView.as_view(), name="protected"),  # Endpoint protegido de prueba

    # Registro de visitas
    path("visits/register/", RegisterUserVisit.as_view(), name="register_visit"),  # Guardar visita de usuario

    # Aliases para compatibilidad con frontend antiguo
    path("api/token/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),  # Login JWT antiguo
]
