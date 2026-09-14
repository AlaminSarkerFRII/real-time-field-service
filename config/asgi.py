import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

# Plain Django ASGI app for now. Becomes a ProtocolTypeRouter (http -> this,
# websocket -> Channels) once the real-time layer is added — see
# docs/architecture.md #2 and docs/repo-structure.md.
application = get_asgi_application()
