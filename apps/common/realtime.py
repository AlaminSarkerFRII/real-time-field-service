from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def send_to_group(group: str, event_type: str, payload: dict[str, Any]) -> None:
    """The one call site sync code (services.py, Celery tasks) ever uses to
    reach the channel layer — docs/data-flow-diagram.md process 3.0. Async
    consumers broadcasting their own events use self.channel_layer directly
    instead; async_to_sync can't be called from inside a running event loop.

    event_type must be dotted (e.g. "job.update") — Channels turns that into
    a call to job_update(self, event) on any consumer subscribed to `group`.
    """
    channel_layer = get_channel_layer()
    assert channel_layer is not None, "CHANNEL_LAYERS is not configured"
    async_to_sync(channel_layer.group_send)(group, {"type": event_type, **payload})
