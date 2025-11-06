from django.contrib import admin
from django.urls import path, include  # path y include deben importarse
        # si usas vista raíz

urlpatterns = [
    path('', include('core.urls')),                 # raíz
  
    path('admin/', admin.site.urls),

    # Música
    path('musica/v1/', include('musica.urls')),

    # API2 (por ejemplo, canciones, artistas, eventos)
    path('api2/v1/', include('api2.urls')),

    # Monedero
    path('monedero/v1/', include('monedero.urls')),

   
]