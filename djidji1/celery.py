import os
from celery import Celery

# Establecer la configuración de Django para Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'djidji1.settings')

app = Celery('djidji1')

# Configurar Celery desde las settings de Django
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-descubrir tareas en todas las apps instaladas
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')