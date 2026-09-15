from django.urls import path

from apps.jobs.consumers import AgentConsumer, DispatchConsumer, JobConsumer

# django.urls.path() is the documented way to build Channels routes, but
# django-stubs types it for HTTP views only and channels-stubs' URLRouter
# wants its own _ExtendedURLPattern — neither stub models this well-known
# interop pattern. Real code, stub gap; see config/asgi.py's URLRouter call.
websocket_urlpatterns = [
    path("ws/dispatch/", DispatchConsumer.as_asgi()),  # type: ignore[arg-type]
    path("ws/agent/", AgentConsumer.as_asgi()),  # type: ignore[arg-type]
    path("ws/jobs/<uuid:job_id>/", JobConsumer.as_asgi()),  # type: ignore[arg-type]
]
