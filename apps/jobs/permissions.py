from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.common.auth import current_user

from .models import Job


class IsJobParticipant(BasePermission):
    """Dispatcher in the job's org, the assigned agent, or the customer.

    Defense-in-depth alongside JobQuerySet.visible_to: that queryset already
    makes a non-participant's job invisible (404 on retrieve); this
    independently blocks access if that scoping is ever missed — see
    docs/system-design.md #6."""

    def has_object_permission(self, request: Request, view: APIView, obj: Job) -> bool:
        user = current_user(request)
        if user.is_superuser:
            return True
        if user.role == User.Role.DISPATCHER:
            return obj.organization_id == user.organization_id
        if user.role == User.Role.AGENT:
            return obj.agent_id == user.id
        if user.role == User.Role.CUSTOMER:
            return obj.customer_id == user.id
        return False


class CanTransitionStatus(BasePermission):
    """Dispatcher (same org) or the assigned agent may change status —
    never the customer, per docs/architecture.md #5's REST contract."""

    def has_object_permission(self, request: Request, view: APIView, obj: Job) -> bool:
        user = current_user(request)
        if user.is_superuser:
            return True
        if user.role == User.Role.DISPATCHER:
            return obj.organization_id == user.organization_id
        if user.role == User.Role.AGENT:
            return obj.agent_id == user.id
        return False
