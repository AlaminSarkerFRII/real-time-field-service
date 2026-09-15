from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin
from django.http import HttpRequest

from .models import Job, JobEvent, Notification

# See apps/accounts/admin.py — Django's real ModelAdmin isn't subscriptable
# at runtime, only the stub is generic.
if TYPE_CHECKING:
    _JobAdminBase = admin.ModelAdmin[Job]
    _JobEventAdminBase = admin.ModelAdmin[JobEvent]
    _NotificationAdminBase = admin.ModelAdmin[Notification]
else:
    _JobAdminBase = admin.ModelAdmin
    _JobEventAdminBase = admin.ModelAdmin
    _NotificationAdminBase = admin.ModelAdmin


@admin.register(Job)
class JobAdmin(_JobAdminBase):
    list_display = [
        "reference",
        "status",
        "priority",
        "organization",
        "agent",
        "customer",
        "scheduled_for",
    ]
    list_filter = ["status", "priority", "organization"]
    search_fields = ["reference", "address"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(JobEvent)
class JobEventAdmin(_JobEventAdminBase):
    # Append-only audit trail — the admin can look, never touch.
    list_display = ["job", "from_status", "to_status", "actor", "created_at"]
    list_filter = ["to_status"]
    readonly_fields = [f.name for f in JobEvent._meta.fields]

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: JobEvent | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: JobEvent | None = None) -> bool:
        return False


@admin.register(Notification)
class NotificationAdmin(_NotificationAdminBase):
    list_display = ["kind", "recipient", "job", "read_at", "created_at"]
    list_filter = ["kind"]
    readonly_fields = [f.name for f in Notification._meta.fields]

    def has_add_permission(self, request: HttpRequest) -> bool:
        # Only Celery tasks create these — see apps/jobs/tasks.py.
        return False
