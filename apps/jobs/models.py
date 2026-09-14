import secrets
import string
import uuid

from django.db import models

from apps.accounts.models import Organization, User

from .state_machine import JobStatus


def default_reference() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


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
