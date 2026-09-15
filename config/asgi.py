import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

# get_asgi_application() calls django.setup() as a side effect — it must run
# before anything below imports a module that touches models (Channels'
# documented ordering requirement).
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402

from apps.accounts.ws_auth import JWTAuthMiddleware  # noqa: E402
from config.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": JWTAuthMiddleware(URLRouter(websocket_urlpatterns)),  # type: ignore[arg-type]
    }
)
