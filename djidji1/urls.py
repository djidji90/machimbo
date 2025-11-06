from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),

    # Core API
    path('api/core/', include('core.urls')),

    # Redirigir home "/" directamente a la info de la API
    path('', RedirectView.as_view(url='/api/core/', permanent=False)),
]
