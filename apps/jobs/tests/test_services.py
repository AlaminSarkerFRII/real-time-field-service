import pytest

from apps.accounts.tests.factories import AgentFactory, DispatcherFactory
from apps.jobs import services
from apps.jobs.models import JobEvent
from apps.jobs.state_machine import IllegalTransitionError, JobStatus
from apps.jobs.tests.factories import JobFactory

pytestmark = pytest.mark.django_db


def test_transition_updates_status_and_logs_event() -> None:
    job = JobFactory()
    dispatcher = DispatcherFactory(organization=job.organization)
    agent = AgentFactory(organization=job.organization)

    updated = services.assign(job=job, agent=agent, actor=dispatcher)
    updated = services.transition(job=updated, to_status=JobStatus.EN_ROUTE, actor=agent)

    assert updated.status == JobStatus.EN_ROUTE
    events = list(updated.events.order_by("created_at"))
    assert [e.to_status for e in events] == [JobStatus.ASSIGNED, JobStatus.EN_ROUTE]
    assert events[-1].from_status == JobStatus.ASSIGNED
    assert events[-1].actor == agent


def test_transition_rejects_illegal_move_without_side_effects() -> None:
    job = JobFactory()  # status=new
    dispatcher = DispatcherFactory(organization=job.organization)

    with pytest.raises(IllegalTransitionError):
        services.transition(job=job, to_status=JobStatus.COMPLETED, actor=dispatcher)

    job.refresh_from_db()
    assert job.status == JobStatus.NEW
    assert not JobEvent.objects.filter(job=job).exists()


def test_assign_sets_agent_and_transitions_to_assigned() -> None:
    job = JobFactory()
    agent = AgentFactory(organization=job.organization)
    dispatcher = DispatcherFactory(organization=job.organization)

    updated = services.assign(job=job, agent=agent, actor=dispatcher)

    assert updated.status == JobStatus.ASSIGNED
    assert updated.agent == agent


def test_assign_twice_raises() -> None:
    job = JobFactory()
    agent = AgentFactory(organization=job.organization)
    dispatcher = DispatcherFactory(organization=job.organization)
    services.assign(job=job, agent=agent, actor=dispatcher)

    with pytest.raises(IllegalTransitionError):
        services.assign(job=job, agent=agent, actor=dispatcher)
