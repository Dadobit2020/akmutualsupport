from .base import *
from decouple import config

DEBUG = config("DEBUG", default=False, cast=bool)

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

_secure = not DEBUG

SECURE_SSL_REDIRECT = _secure
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 31536000 if _secure else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = _secure
SECURE_HSTS_PRELOAD = _secure
SESSION_COOKIE_SECURE = _secure
CSRF_COOKIE_SECURE = _secure

CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", default="", cast=Csv())

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "apps": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
