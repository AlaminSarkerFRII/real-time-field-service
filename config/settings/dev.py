from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Serve each app's static/ directly (no collectstatic needed in dev) — the
# same convenience runserver used to give for free.
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = True
