from datetime import timedelta
from pathlib import Path

import environ
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "channels",
    "apps.accounts",
    "apps.jobs",
]

AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Serves static files from any ASGI server (uvicorn included) — Django's
    # runserver-only auto-static-serving doesn't apply once uvicorn is the
    # dev server too (see docs/architecture.md #2's ASGI-first decision).
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

ASGI_APPLICATION = "config.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [env("REDIS_URL", default="redis://localhost:6379/0")]},
    },
}

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://fieldsync:fieldsync@localhost:5432/fieldsync",
    ),
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "FieldSync API",
    "DESCRIPTION": "Real-time field-service dispatch — see docs/architecture.md.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# 15-minute access token on stateless ASGI replicas, per docs/tech-stack.md D4
# and docs/system-design.md §6 (L2 · AuthN).
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# Redis doubles as the Celery broker/result backend — accepted trade-off,
# see docs/system-design.md #9 risk R-1.
CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# Two queues, per docs/tech-stack.md's supporting-stack decision: a slow
# nightly report can never delay a live notification.
CELERY_TASK_ROUTES = {
    "apps.jobs.tasks.notify_status_change": {"queue": "realtime"},
    "apps.jobs.tasks.send_upcoming_reminders": {"queue": "realtime"},
    "apps.jobs.tasks.expire_stale_locations": {"queue": "realtime"},
    "apps.jobs.tasks.daily_ops_report": {"queue": "reports"},
}

CELERY_BEAT_SCHEDULE = {
    "send-upcoming-reminders": {
        "task": "apps.jobs.tasks.send_upcoming_reminders",
        "schedule": crontab(minute="*/15"),
    },
    "expire-stale-locations": {
        "task": "apps.jobs.tasks.expire_stale_locations",
        "schedule": crontab(minute="*/2"),
    },
    "daily-ops-report": {
        "task": "apps.jobs.tasks.daily_ops_report",
        "schedule": crontab(hour=2, minute=0),
    },
}
