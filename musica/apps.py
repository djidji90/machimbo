from django.apps import AppConfig

class MusicaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'musica'

    def ready(self):
        # Importar señales de la app musica para que se registren
        import musica.signals
