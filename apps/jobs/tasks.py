import logging
from datetime import timedelta

from celery import shared_task
from django.db.models import Count
from django.utils import timezone

from apps.accounts.models import AgentProfile

from .models import Job, JobEvent, Notification
from .state_machine import JobStatus

logger = logging.getLogger(__name__)

STATUS_NOTIFICATION_KIND: dict[str, Notification.Kind] = {
    JobStatus.ASSIGNED: Notification.Kind.JOB_ASSIGNED,
    JobStatus.EN_ROUTE: Notification.Kind.JOB_EN_ROUTE,
    JobStatus.ON_SITE: Notification.Kind.JOB_ON_SITE,
    JobStatus.COMPLETED: Notification.Kind.JOB_COMPLETED,
    JobStatus.CANCELLED: Notification.Kind.JOB_CANCELLED,
}

STATUS_MESSAGE: dict[str, str] = {
    JobStatus.ASSIGNED: "A technician has been assigned to your job {reference}.",
    JobStatus.EN_ROUTE: "Your technician is on the way for job {reference}.",
    JobStatus.ON_SITE: "Your technician has arrived for job {reference}.",
    JobStatus.COMPLETED: "Job {reference} is complete.",
    JobStatus.CANCELLED: "Job {reference} was cancelled.",
}


@shared_task(autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 5})
def notify_status_change(job_id: str) -> None:
    """Fired via .delay() from apps.jobs.services after a status change —
    docs/architecture.md #7. Idempotent per (job, kind, recipient): a retry
    or duplicate call is a no-op, not a duplicate notification. The WS push
    to user.<id> is added once the real-time layer exists (architecture.md
    #3) — today this task's job is just the Notification row + logged send."""
    job = Job.objects.select_related("customer").get(pk=job_id)
    kind = STATUS_NOTIFICATION_KIND.get(job.status)
    if kind is None:
        return

    body = STATUS_MESSAGE[job.status].format(reference=job.reference)
    _, created = Notification.objects.get_or_create(
        job=job,
        kind=kind,
        recipient=job.customer,
        defaults={"title": f"Job {job.reference} update", "body": body},
    )
    if created:
        # "Send" the email/SMS — logged in dev, a real provider in prod.
        logger.info(
            "notify.sent", extra={"recipient": job.customer.email, "kind": kind, "body": body}
        )


@shared_task
def send_upcoming_reminders(window_minutes: int = 60) -> int:
    """Beat · every 15 min — docs/architecture.md #7. Idempotent via the
    same (job, kind, recipient) constraint as notify_status_change."""
    now = timezone.now()
    due = Job.objects.select_related("customer").filter(
        scheduled_for__isnull=False,
        scheduled_for__gte=now,
        scheduled_for__lte=now + timedelta(minutes=window_minutes),
        status__in=[JobStatus.NEW, JobStatus.ASSIGNED],
    )
    sent = 0
    for job in due:
        _, created = Notification.objects.get_or_create(
            job=job,
            kind=Notification.Kind.UPCOMING_REMINDER,
            recipient=job.customer,
            defaults={
                "title": f"Reminder: job {job.reference}",
                "body": f"Your appointment for job {job.reference} is coming up soon.",
            },
        )
        if created:
            sent += 1
            logger.info(
                "reminder.sent", extra={"recipient": job.customer.email, "job": job.reference}
            )
    return sent


@shared_task
def expire_stale_locations(stale_after_minutes: int = 5) -> int:
    """Beat · every 2 min — docs/architecture.md #7."""
    threshold = timezone.now() - timedelta(minutes=stale_after_minutes)
    updated = AgentProfile.objects.filter(
        status=AgentProfile.Status.ONLINE, last_ping_at__lt=threshold
    ).update(status=AgentProfile.Status.OFFLINE)
    if updated:
        logger.info("agents.expired", extra={"count": updated})
    return updated


@shared_task
def daily_ops_report() -> dict[str, int]:
    """Beat · nightly — docs/architecture.md #7. Aggregates the day's
    JobEvents per organization; a natural place to generate a CSV/PDF
    artifact later (docs/system-design.md #7) — logged for now."""
    since = timezone.now() - timedelta(days=1)
    counts = (
        JobEvent.objects.filter(created_at__gte=since)
        .values("job__organization__name")
        .annotate(total=Count("id"))
    )
    report = {row["job__organization__name"]: row["total"] for row in counts}
    logger.info("ops.daily_report", extra={"report": report})
    return report
