from .base import *  # noqa: F401,F403

DEBUG = False
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")  # noqa: F405 — env comes from base.py's star import

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# Compressed, cache-bustable filenames — requires `manage.py collectstatic`
# as an explicit release step (docs/system-design.md #7.1), never implicit
# on container start.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
