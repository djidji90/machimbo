web: python manage.py migrate && gunicorn djidji1.wsgi:application --bind 0.0.0.0:$PORT
worker: celery -A djidji1 worker --loglevel=info
beat: celery -A djidji1 beat --loglevel=info