from django.apps import AppConfig

class MonederoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'monedero'

    def ready(self):
        # Importa señales para que se registren
        import monedero.signals
        # Importa tareas Celery para que se registren
        import monedero.tasks