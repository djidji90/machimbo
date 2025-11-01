# Procfile

# Proceso web: Django con Gunicorn
web: gunicorn djidji1.wsgi --log-file -

# Worker de Celery para tareas asíncronas
worker: celery -A djidji1 worker --loglevel=info

# Beat de Celery (opcional, para tareas programadas)
beat: celery -A djidji1 beat --loglevel=info
