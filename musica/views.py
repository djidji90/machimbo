import logging
import requests
from django.conf import settings
from django.utils.timezone import now

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import UserVisit
from .serializers import RegisterSerializer

logger = logging.getLogger(__name__)

# -----------------------------
# Utilidades
# -----------------------------
def get_client_ip(request):
    """Obtiene la IP real del cliente, considerando proxies."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0]
    return request.META.get("REMOTE_ADDR", "127.0.0.1")


def get_location_data(ip):
    """Obtiene información de geolocalización de la IP."""
    api_key = getattr(settings, "API_INFO_KEY", None)
    if not api_key:
        logger.warning("API_INFO_KEY no está configurada en settings.")
        return {}

    url = f"https://apiinfo.com/data?ip={ip}&key={api_key}"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.Timeout:
        logger.error(f"Timeout al obtener datos de geolocalización para IP {ip}")
    except requests.RequestException as e:
        logger.error(f"Error al obtener datos de geolocalización: {str(e)}")
    return {}


def log_user_visit(user, request):
    """Registra una visita de usuario en la base de datos."""
    ip = get_client_ip(request)
    location_data = get_location_data(ip) or {}

    es_recurrente = False
    if user:
        # Si existen otras visitas diferentes a la actual
        es_recurrente = UserVisit.objects.filter(user=user).exclude(ip=ip).exists()

    visit = UserVisit.objects.create(
        user=user,
        ip=ip,
        ciudad=location_data.get("city", "Desconocido"),
        region=location_data.get("region", "Desconocido"),
        pais=location_data.get("country", "Desconocido"),
        latitud=location_data.get("latitude"),
        longitud=location_data.get("longitude"),
        proveedor=location_data.get("isp", "Desconocido"),
        user_agent=request.META.get("HTTP_USER_AGENT", "Desconocido"),
        navegador=location_data.get("browser", "Desconocido"),
        sistema_operativo=location_data.get("os", "Desconocido"),
        es_recurrente=es_recurrente,
        url_referencia=request.META.get("HTTP_REFERER", "Desconocido"),
        fecha_visita=now()
    )
    return visit

# -----------------------------
# Registro de usuarios
# -----------------------------
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            try:
                user = serializer.save()
                refresh = RefreshToken.for_user(user)

                # Registrar la visita
                log_user_visit(user, request)

                return Response(
                    {
                        "message": "Usuario registrado exitosamente.",
                        "data": serializer.data,
                        "tokens": {
                            "refresh": str(refresh),
                            "access": str(refresh.access_token),
                        },
                    },
                    status=status.HTTP_201_CREATED
                )
            except Exception as e:
                return Response(
                    {"error": f"Error al registrar usuario: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


# -----------------------------
# Login con JWT y registro de visitas
# -----------------------------
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        request = self.context["request"]
        user = self.user

        # Registrar la visita
        log_user_visit(user, request)
        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


# -----------------------------
# Endpoints protegidos
# -----------------------------
class ProtectedView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {"message": "¡Acceso permitido solo para usuarios autenticados!"},
            status=status.HTTP_200_OK
        )


class RegisterUserVisit(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        visit = log_user_visit(user, request)
        return Response(
            {
                "message": "Visita registrada con éxito",
                "data": {"ip": visit.ip, "ciudad": visit.ciudad, "pais": visit.pais}
            },
            status=status.HTTP_201_CREATED
        )


# -----------------------------
# Información del usuario actual
# -----------------------------
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user(request):
    user = request.user
    return Response({
        "id": user.id,
        "username": user.username,
        "is_verified": getattr(user, "is_verified", False)
    })
