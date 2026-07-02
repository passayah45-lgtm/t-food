from django.apps import AppConfig


class MarketsConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'markets'

    def ready(self):
        import markets.signals  # noqa: F401
