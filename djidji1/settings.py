"""
Django settings for djidji1 project (Producción).
Adaptado para despliegue en Railway u otros proveedores.
"""
import os
from pathlib import Path
from decimal import Decimal
from datetime import timedelta
from dotenv import load_dotenv
import dj_database_url
from django.core.exceptions import ImproperlyConfigured

# Cargar variables de entorno
load_dotenv()

# ------------------------------
# Paths
# ------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# ------------------------------
# Seguridad
# ------------------------------
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured("La variable de entorno SECRET_KEY no está definida")

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", SECRET_KEY)

DEBUG = False

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "").split(",")

# ------------------------------
# Aplicaciones
# ------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'corsheaders',
    'django_celery_beat',
    'django_celery_results',
    'rest_framework',
    'rest_framework.authtoken',
    'rest_framework_simplejwt',
    'django_filters',
    'drf_yasg',

    # Local
    'musica',
    'api2',
    'monedero.apps.MonederoConfig',
    'tienda',
]

AUTH_USER_MODEL = 'musica.CustomUser'

# ------------------------------
# Middleware
# ------------------------------
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

# ------------------------------
# Templates
# ------------------------------
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

# ------------------------------
# Base de datos
# ------------------------------
DATABASES = {
    'default': dj_database_url.config(
        conn_max_age=600,
        ssl_require=True
    )
}

# ------------------------------
# Cache / Redis
# ------------------------------
REDIS_URL = os.getenv("REDIS_URL")
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL or "redis://localhost:6379/1",
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}

# ------------------------------
# Celery
# ------------------------------
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_ALWAYS_EAGER = False
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Africa/Malabo'

# ------------------------------
# Celery Beat (ejemplo)
# ------------------------------
from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    'liberar-fondos': {
        'task': 'ventas.tasks.liberar_fondos_retenidos',
        'schedule': crontab(minute='*/15'),
    },
    'actualizar-destacados': {
        'task': 'ventas.tasks.actualizar_productos_destacados',
        'schedule': crontab(hour=3, minute=0),
    },
}

# ------------------------------
# REST Framework y JWT
# ------------------------------
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': JWT_SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'username',
    'USER_ID_CLAIM': 'user_id'
}

REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
    'DEFAULT_THROTTLE_RATES': {
        'transacciones': '5/minute',
        'transferencias': '10/hour',
        'anon': '100/hour',
        'user': '1000/hour'
    },
}

# ------------------------------
# Archivos estáticos y media
# ------------------------------
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ------------------------------
# CORS
# ------------------------------
CORS_ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")

# ------------------------------
# Seguridad adicional
# ------------------------------
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 3600
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

# ------------------------------
# Internacionalización
# ------------------------------
LANGUAGE_CODE = 'es-us'
TIME_ZONE = 'Africa/Malabo'
USE_I18N = True
USE_TZ = True

# ------------------------------
# Monedero y wallet
# ------------------------------
WALLET_SETTINGS = {
    'MAX_PIN_ATTEMPTS': 3,
    'PIN_LOCK_DURATION_MINUTES': 30,
    'DAILY_LIMIT_DEFAULT': Decimal('1000000.00'),
    'CURRENCIES': [
        ('USD', 'Dólares Estadounidenses'),
        ('EUR', 'Euros'),
        ('XAF', 'Franco CFA Centroafricano'),
        ('XOF', 'Franco CFA Occidental'),
    ]
}

DEFAULT_CURRENCY = 'XAF'

MONEDERO_CONFIG = {
    'SALDO_MINIMO': Decimal('2000.00'),
    'MAX_RETIRO_DIARIO': Decimal('1000000.00'),
    'MAX_RECARGA': Decimal('100000.00'),
    'INTENTOS_PIN': 3,
    'TIEMPO_BLOQUEO_MINUTOS': 10,
    'COMISION_TRANSFERENCIA': Decimal('0.01'),
}

# ------------------------------
# Logging
# ------------------------------
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
    },
    'loggers': {
        'monedero.tasks': {'handlers': ['celery_file', 'celery_errors'], 'level': 'INFO', 'propagate': True},
        'django': {'handlers': ['django_errors'], 'level': 'ERROR', 'propagate': True},
    },
}
