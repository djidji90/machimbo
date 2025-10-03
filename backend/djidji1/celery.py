import os
import eventlet
eventlet.monkey_patch()  # Debe ser la PRIMERA línea

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'djidji1.settings')

app = Celery('djidji1')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()