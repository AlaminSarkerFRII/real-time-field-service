from .base import *  # noqa: F401,F403

DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# No broker needed in tests — tasks run synchronously, in-process.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# No Redis needed for channel-layer tests either — Channels' own documented
# testing pattern.
CHANNEL_LAYERS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
}

# No collectstatic in tests either — same as dev. AUTOREFRESH defaults to
# DEBUG (False here), which would make WhiteNoise eagerly scan STATIC_ROOT
# at startup and warn since it doesn't exist; set explicitly instead.
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = True
