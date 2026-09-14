from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class HasRole(BasePermission):
    """Base class for a fixed-role check. Subclass and set allowed_roles —
    see system-design.md §6 (L3 · AuthZ)."""

    allowed_roles: frozenset[str] = frozenset()

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.role in self.allowed_roles)


class IsDispatcher(HasRole):
    allowed_roles = frozenset({"dispatcher"})


class IsAgent(HasRole):
    allowed_roles = frozenset({"agent"})


class IsCustomer(HasRole):
    allowed_roles = frozenset({"customer"})
