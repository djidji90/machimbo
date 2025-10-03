import geoip2.database
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from .models import UserVisit
import user_agents

class UserVisitMiddleware(MiddlewareMixin):
    def process_request(self, request):
        ip = self.get_client_ip(request)
        user_agent_str = request.META.get("HTTP_USER_AGENT", "")
        ua = user_agents.parse(user_agent_str)

        ciudad = region = pais = lat = lon = proveedor = None

        try:
            reader = geoip2.database.Reader(f"{settings.GEOIP_PATH}/GeoLite2-City.mmdb")
            response = reader.city(ip)
            ciudad = response.city.name
            region = response.subdivisions.most_specific.name
            pais = response.country.name
            lat = response.location.latitude
            lon = response.location.longitude
            reader.close()
        except Exception:
            pass

        UserVisit.objects.create(
            user=request.user if request.user.is_authenticated else None,
            ip=ip,
            ciudad=ciudad,
            region=region,
            pais=pais,
            latitud=lat,
            longitud=lon,
            proveedor=None,  # aquí si quieres luego usar ASN db (GeoLite2-ASN.mmdb)
            user_agent=user_agent_str,
            navegador=ua.browser.family,
            sistema_operativo=ua.os.family,
            url_referencia=request.META.get("HTTP_REFERER", ""),
            es_recurrente=False,  # lo puedes calcular con lógica extra
        )

    def get_client_ip(self, request):
        """Obtiene la IP real del cliente detrás de proxies"""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0]
        return request.META.get("REMOTE_ADDR")
