"""
Django settings para djidji1 (Producción).
Optimizado para despliegue en Railway.
"""

from pathlib import Path
from datetime import timedelta
from decimal import Decimal
import os
from dotenv import load_dotenv

# -----------------------------------------------------------------------------
#  BASE Y VARIABLES DE ENTORNO
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# Cargar variables de entorno desde .env
load_dotenv(BASE_DIR / '.env')

# -----------------------------------------------------------------------------
#  SEGURIDAD
# -----------------------------------------------------------------------------
SECRET_KEY = os.getenv('SECRET_KEY', 'clave-por-defecto-cambiar-en-produccion')
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '*').split(',')

# -----------------------------------------------------------------------------
#  APLICACIONES
# -----------------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Paquetes externos
    'corsheaders',
    'django_celery_beat',
    'django_celery_results',
    'django_filters',
    'drf_yasg',
    'rest_framework',
    'rest_framework.authtoken',
    'rest_framework_simplejwt',


    # Apps internas
    'musica',
    'api2',
    'monedero.apps.MonederoConfig',
    'tienda',
    "core",
]

AUTH_USER_MODEL = 'musica.CustomUser'

# -----------------------------------------------------------------------------
#  MIDDLEWARE
# -----------------------------------------------------------------------------
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'djidji1.urls'

# -----------------------------------------------------------------------------
#  CORS
# -----------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = [
    'https://web-production-a846.up.railway.app',
    'https://djidjimudic.com',
    'https://www.djidjimudic.com',
    'http://localhost:3000',
    'http://127.0.0.1:3000',
]

CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    'https://web-production-a846.up.railway.app',
    'https://*.railway.app',
    'https://djidjimudic.com',
    'https://www.djidjimudic.com',
]

# -----------------------------------------------------------------------------
#  TEMPLATES
# -----------------------------------------------------------------------------
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'djidji1.wsgi.application'

# -----------------------------------------------------------------------------
#  BASE DE DATOS
# -----------------------------------------------------------------------------
# Configuración manual de base de datos desde DATABASE_URL
if os.getenv("RAILWAY_ENV") == "production":
    import dj_database_url
    DATABASES = {
        "default": dj_database_url.parse(os.getenv("DATABASE_URL"))
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# -----------------------------------------------------------------------------
#  REDIS / CACHE / CELERY
# -----------------------------------------------------------------------------
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/1')

# -------------------------------------------------------------------------
# CELERY CONFIGURATION
# -------------------------------------------------------------------------
CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://localhost:6379/1")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Africa/Malabo'
CELERY_ENABLE_UTC = True


# ⚠️ DESACTIVAR CELERY TEMPORALMENTE
if os.getenv("RAILWAY_ENV") == "production":
    CELERY_BROKER_URL = os.getenv("REDIS_URL")
    CELERY_RESULT_BACKEND = os.getenv("REDIS_URL")


# -----------------------------------------------------------------------------
#  JWT / REST FRAMEWORK
# -----------------------------------------------------------------------------
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'username',
    'USER_ID_CLAIM': 'user_id',
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    # ⚡ Configuración de Throttling
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.AnonRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'user': '1000/day',
        'anon': '100/day',
        'upload': '10/hour',  # <--- scope personalizado
    },
}

# Configuración de drf-spectacular (debe estar afuera del diccionario REST_FRAMEWORK)
SPECTACULAR_SETTINGS = {
    'TITLE': 'Djidji API',
    'DESCRIPTION': 'API de música, tienda y monedero de Djidji',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}



# -----------------------------------------------------------------------------
#  SEGURIDAD Y COOKIES
# -----------------------------------------------------------------------------
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_HSTS_SECONDS = 3600
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

# -----------------------------------------------------------------------------
#  ARCHIVOS
# -----------------------------------------------------------------------------
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# -----------------------------------------------------------------------------
#  INTERNACIONALIZACIÓN
# -----------------------------------------------------------------------------
LANGUAGE_CODE = 'es-us'
TIME_ZONE = 'Africa/Malabo'
USE_I18N = True
USE_TZ = True

# -----------------------------------------------------------------------------
#  MONEDERO / WALLET CONFIG
# -----------------------------------------------------------------------------
MONEDERO_CONFIG = {
    'SALDO_MINIMO': Decimal('2000.00'),
    'MAX_RETIRO_DIARIO': Decimal('1000000.00'),
    'MAX_RECARGA': Decimal('100000.00'),
    'INTENTOS_PIN': 3,
    'TIEMPO_BLOQUEO_MINUTOS': 10,
    'COMISION_TRANSFERENCIA': Decimal('0.01'),
}

# -----------------------------------------------------------------------------
#  LOGGING
# -----------------------------------------------------------------------------
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {'format': '{levelname} {asctime} {module} {message}', 'style': '{'},
    },
    'handlers': {
        'celery_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': str(LOG_DIR / 'celery_tasks.log'),
            'formatter': 'verbose',
        },
        'celery_errors': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': str(LOG_DIR / 'celery_errors.log'),
            'formatter': 'verbose',
        },
        'django_errors': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': str(LOG_DIR / 'django_errors.log'),
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'monedero.tasks': {
            'handlers': ['celery_file', 'celery_errors', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'django': {
            'handlers': ['django_errors', 'console'],
            'level': 'ERROR',
            'propagate': True,
        },
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# -----------------------------------------------------------------------------
#  CONFIGURACIONES ADICIONALES
# -----------------------------------------------------------------------------
# Para Railway - manejo de archivos estáticos
#STATICFILES_DIRS = [BASE_DIR / "static",]

# Configuración de email (opcional)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'