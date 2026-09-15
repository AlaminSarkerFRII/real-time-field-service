import secrets
import string
import uuid
from typing import Self

from django.db import models

from apps.accounts.models import Organization, User
from apps.common.querysets import OrgScopedQuerySet

from .state_machine import JobStatus


def default_reference() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


class JobQuerySet(OrgScopedQuerySet["Job"]):
    def visible_to(self, user: User) -> Self:
        """Role-scoped per docs/architecture.md #5: dispatcher sees the whole
        org, agent sees only their assigned jobs, customer sees only their
        own. This is the one place that scoping is implemented."""
        if user.is_superuser:
            return self
        qs = self.for_organization(user.organization_id)
        if user.role == User.Role.AGENT:
            return qs.filter(agent_id=user.id)
        if user.role == User.Role.CUSTOMER:
            return qs.filter(customer_id=user.id)
        return qs


class Job(models.Model):
    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        URGENT = "urgent", "Urgent"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=12, default=default_reference)
    status = models.CharField(max_length=20, choices=JobStatus.choices, default=JobStatus.NEW)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    address = models.CharField(max_length=255)
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    # Nullable: some jobs are ASAP walk-ins with no scheduled time.
    scheduled_for = models.DateTimeField(null=True, blank=True)
    customer = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="jobs_as_customer"
    )
    agent = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="jobs_as_agent",
        null=True,
        blank=True,
    )
    # The authoritative tenant boundary — never derived from customer/agent.
    # See docs/data-model.md, multi-tenancy enforcement.
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="jobs")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = JobQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "reference"], name="unique_job_reference_per_org"
            )
        ]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["agent", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.reference} ({self.status})"


class JobEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="events")
    # Blank on the very first event: there is no status before "new".
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20, choices=JobStatus.choices)
    actor = models.ForeignKey(User, on_delete=models.PROTECT, related_name="job_events")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["job", "created_at"])]

    def __str__(self) -> str:
        return f"{self.job_id}: {self.from_status or '∅'} -> {self.to_status}"


class Notification(models.Model):
    class Kind(models.TextChoices):
        JOB_ASSIGNED = "job_assigned", "Job assigned"
        JOB_EN_ROUTE = "job_en_route", "Agent en route"
        JOB_ON_SITE = "job_on_site", "Agent on site"
        JOB_COMPLETED = "job_completed", "Job completed"
        JOB_CANCELLED = "job_cancelled", "Job cancelled"
        UPCOMING_REMINDER = "upcoming_reminder", "Upcoming appointment reminder"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    # Not in the original data-model.md sketch — added so a Celery retry (or a
    # duplicate beat tick) can be idempotent per (job, kind, recipient)
    # instead of re-sending. Nullable for a future notification that isn't
    # about a specific job.
    job = models.ForeignKey(
        Job, on_delete=models.CASCADE, related_name="notifications", null=True, blank=True
    )
    kind = models.CharField(max_length=30, choices=Kind.choices)
    title = models.CharField(max_length=200)
    body = models.TextField()
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["job", "kind", "recipient"],
                name="unique_notification_per_job_kind_recipient",
            )
        ]
        indexes = [models.Index(fields=["recipient", "read_at"])]

    def __str__(self) -> str:
        return f"{self.kind} -> {self.recipient_id}"
