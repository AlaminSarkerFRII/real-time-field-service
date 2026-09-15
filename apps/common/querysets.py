from typing import Self, TypeVar

from django.db import models

_M = TypeVar("_M", bound=models.Model)


class OrgScopedQuerySet(models.QuerySet[_M]):
    """Base queryset for any model with an `organization` FK. Every
    tenant-scoped queryset in the app should build on this — see
    docs/system-design.md #6 (L3 · AuthZ) and docs/data-model.md's
    multi-tenancy section."""

    def for_organization(self, organization_id: object) -> Self:
        return self.filter(organization_id=organization_id)
