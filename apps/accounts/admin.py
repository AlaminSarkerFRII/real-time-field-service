from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.contrib import admin
from django.contrib.admin.options import InlineModelAdmin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.http import HttpRequest

from .models import AgentProfile, Organization, User

# Django's real ModelAdmin/StackedInline/UserAdmin don't support __class_getitem__
# at runtime — only the django-stubs .pyi declares them Generic. Subscript them
# for mypy only, and inherit the plain class at runtime, or admin.py crashes
# the moment Django's admin autodiscovery imports it for real.
if TYPE_CHECKING:
    _OrganizationAdminBase = admin.ModelAdmin[Organization]
    _AgentProfileInlineBase = admin.StackedInline[AgentProfile, User]
    _UserAdminBase = DjangoUserAdmin[User]
else:
    _OrganizationAdminBase = admin.ModelAdmin
    _AgentProfileInlineBase = admin.StackedInline
    _UserAdminBase = DjangoUserAdmin


@admin.register(Organization)
class OrganizationAdmin(_OrganizationAdminBase):
    list_display = ["name", "timezone", "created_at"]
    search_fields = ["name"]


class AgentProfileInline(_AgentProfileInlineBase):
    model = AgentProfile
    can_delete = False


@admin.register(User)
class UserAdmin(_UserAdminBase):
    model = User
    ordering = ["email"]
    list_display = ["email", "full_name", "role", "organization", "is_active", "is_staff"]
    list_filter = ["role", "is_active", "is_staff", "organization"]
    search_fields = ["email", "full_name"]
    inlines = [AgentProfileInline]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("full_name", "role", "organization")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Important dates", {"fields": ("last_login", "created_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "role", "organization", "password1", "password2"),
            },
        ),
    )
    readonly_fields = ["last_login", "created_at"]

    def get_inline_instances(
        self, request: HttpRequest, obj: User | None = None
    ) -> list[InlineModelAdmin[Any, Any]]:
        # Only show the agent-profile inline once the user exists and is an agent.
        if not obj or obj.role != User.Role.AGENT:
            return []
        return super().get_inline_instances(request, obj)
