
"""
URL configuration for primera project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # Ruta para el panel de administración
    path('admin/', admin.site.urls),
      # Ruta para la API de la aplicación 'djidji1'
    path('api/', include('musica.urls')),
    path('api2/', include('api2.urls')),
    path('tienda/', include('tienda.urls')),
    path('ventas/', include('ventas.urls')),
    path('monedero/', include('monedero.urls')),
    
    # Ruta para la aplicación 'proyect
]