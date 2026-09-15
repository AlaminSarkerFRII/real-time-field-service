from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import AgentProfile
from apps.accounts.tests.factories import AgentFactory, AgentProfileFactory, DispatcherFactory
from apps.jobs import services, tasks
from apps.jobs.models import Notification
from apps.jobs.state_machine import JobStatus
from apps.jobs.tests.factories import JobFactory

pytestmark = pytest.mark.django_db


def test_notify_status_change_creates_notification_for_customer() -> None:
    job = JobFactory()
    dispatcher = DispatcherFactory(organization=job.organization)
    agent = AgentFactory(organization=job.organization)
    services.assign(job=job, agent=agent, actor=dispatcher)

    tasks.notify_status_change(str(job.id))

    notification = Notification.objects.get(job=job, kind=Notification.Kind.JOB_ASSIGNED)
    assert notification.recipient == job.customer
    assert job.reference in notification.body


def test_notify_status_change_is_idempotent() -> None:
    job = JobFactory()
    dispatcher = DispatcherFactory(organization=job.organization)
    agent = AgentFactory(organization=job.organization)
    services.assign(job=job, agent=agent, actor=dispatcher)

    tasks.notify_status_change(str(job.id))
    tasks.notify_status_change(str(job.id))  # simulate a retry

    assert Notification.objects.filter(job=job, kind=Notification.Kind.JOB_ASSIGNED).count() == 1


def test_notify_status_change_no_op_for_new_status() -> None:
    job = JobFactory()  # still "new" — no notification kind mapped

    tasks.notify_status_change(str(job.id))

    assert not Notification.objects.filter(job=job).exists()


def test_send_upcoming_reminders_notifies_jobs_in_window() -> None:
    soon = JobFactory(scheduled_for=timezone.now() + timedelta(minutes=30))
    later = JobFactory(scheduled_for=timezone.now() + timedelta(days=2))
    unscheduled = JobFactory()

    sent = tasks.send_upcoming_reminders(window_minutes=60)

    assert sent == 1
    assert Notification.objects.filter(job=soon, kind=Notification.Kind.UPCOMING_REMINDER).exists()
    assert not Notification.objects.filter(job=later).exists()
    assert not Notification.objects.filter(job=unscheduled).exists()


def test_send_upcoming_reminders_is_idempotent() -> None:
    job = JobFactory(scheduled_for=timezone.now() + timedelta(minutes=10))

    first = tasks.send_upcoming_reminders(window_minutes=60)
    second = tasks.send_upcoming_reminders(window_minutes=60)

    assert first == 1
    assert second == 0
    remaining = Notification.objects.filter(job=job, kind=Notification.Kind.UPCOMING_REMINDER)
    assert remaining.count() == 1


def test_expire_stale_locations_flips_stale_agents_offline() -> None:
    stale = AgentProfileFactory(
        status=AgentProfile.Status.ONLINE, last_ping_at=timezone.now() - timedelta(minutes=10)
    )
    fresh = AgentProfileFactory(status=AgentProfile.Status.ONLINE, last_ping_at=timezone.now())

    updated = tasks.expire_stale_locations(stale_after_minutes=5)

    assert updated == 1
    stale.refresh_from_db()
    fresh.refresh_from_db()
    assert stale.status == AgentProfile.Status.OFFLINE
    assert fresh.status == AgentProfile.Status.ONLINE


def test_daily_ops_report_aggregates_by_organization() -> None:
    job = JobFactory()
    dispatcher = DispatcherFactory(organization=job.organization)
    agent = AgentFactory(organization=job.organization)
    services.assign(job=job, agent=agent, actor=dispatcher)
    services.transition(job=job, to_status=JobStatus.EN_ROUTE, actor=agent)

    report = tasks.daily_ops_report()

    assert report[job.organization.name] == 2
