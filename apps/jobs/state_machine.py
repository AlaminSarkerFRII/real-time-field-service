from django.db import models


class JobStatus(models.TextChoices):
    NEW = "new", "New"
    ASSIGNED = "assigned", "Assigned"
    EN_ROUTE = "en_route", "En route"
    ON_SITE = "on_site", "On site"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


# See docs/architecture.md #4 and docs/data-model.md — checked in services.py,
# never bypassed by a direct model save.
TRANSITIONS: dict[str, frozenset[str]] = {
    JobStatus.NEW: frozenset({JobStatus.ASSIGNED}),
    JobStatus.ASSIGNED: frozenset({JobStatus.EN_ROUTE, JobStatus.CANCELLED}),
    JobStatus.EN_ROUTE: frozenset({JobStatus.ON_SITE}),
    JobStatus.ON_SITE: frozenset({JobStatus.COMPLETED}),
    JobStatus.COMPLETED: frozenset(),
    JobStatus.CANCELLED: frozenset(),
}


class IllegalTransitionError(ValueError):
    pass


def validate_transition(from_status: str, to_status: str) -> None:
    allowed = TRANSITIONS.get(from_status)
    if allowed is None:
        raise IllegalTransitionError(f"Unknown status: {from_status!r}")
    if to_status not in allowed:
        raise IllegalTransitionError(f"Cannot transition from {from_status!r} to {to_status!r}")
