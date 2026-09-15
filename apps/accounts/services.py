from django.utils import timezone

from .models import AgentProfile, User


def record_location(*, agent: User, lat: float, lng: float) -> AgentProfile:
    """The only writer of AgentProfile's location fields — called from
    AgentConsumer.receive() on a location.ping. DFD process 2.0 in
    docs/data-flow-diagram.md. A ping also means the agent is online."""
    profile, _ = AgentProfile.objects.update_or_create(
        user=agent,
        defaults={
            "last_lat": lat,
            "last_lng": lng,
            "last_ping_at": timezone.now(),
            "status": AgentProfile.Status.ONLINE,
        },
    )
    return profile
