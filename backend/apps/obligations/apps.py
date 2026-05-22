from django.apps import AppConfig


class ObligationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.obligations"
    label = "obligations"

    def ready(self):
        import apps.obligations.signals  # noqa: F401
