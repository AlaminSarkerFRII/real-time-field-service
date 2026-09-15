from django.db import transaction

from apps.accounts.models import User

from .models import Job, JobEvent
from .state_machine import JobStatus, validate_transition


def assign(*, job: Job, agent: User, actor: User) -> Job:
    """Sets the agent and transitions new -> assigned atomically, so two
    dispatchers can't race to assign the same job (or grab the same agent
    for two jobs) at once — docs/architecture.md #9 advanced-Python target."""
    with transaction.atomic():
        locked = Job.objects.select_for_update().get(pk=job.pk)
        validate_transition(locked.status, JobStatus.ASSIGNED)
        from_status = locked.status
        locked.agent = agent
        locked.status = JobStatus.ASSIGNED
        locked.save(update_fields=["agent", "status", "updated_at"])
        JobEvent.objects.create(
            job=locked, from_status=from_status, to_status=JobStatus.ASSIGNED, actor=actor
        )
    return locked


def transition(*, job: Job, to_status: str, actor: User) -> Job:
    """The single source of truth for a job status change — the REST view and
    the WS consumer both call this, never Job.save() directly. See
    docs/architecture.md #3 and docs/data-flow-diagram.md process 1.0."""
    with transaction.atomic():
        locked = Job.objects.select_for_update().get(pk=job.pk)
        validate_transition(locked.status, to_status)
        from_status = locked.status
        locked.status = to_status
        locked.save(update_fields=["status", "updated_at"])
        JobEvent.objects.create(
            job=locked, from_status=from_status, to_status=to_status, actor=actor
        )
    return locked
