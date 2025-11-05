import os
from celery import Celery

# Configuración base
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'djidji1.settings')

app = Celery('djidji1')

# Cargar configuración desde settings.py
app.config_from_object('django.conf:settings', namespace='CELERY')

# Descubre automáticamente las tareas registradas en las apps instaladas
app.autodiscover_tasks()

# Ajustes de entorno (útiles en Railway)
app.conf.update(
    broker_connection_retry_on_startup=True,
    broker_heartbeat=0,
    worker_max_tasks_per_child=100,
    timezone='Africa/Malabo',
    enable_utc=True,
)

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"[DEBUG] Celery Task: {self.request!r}")
