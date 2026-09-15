import pytest
from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.accounts.tests.factories import DispatcherFactory

pytestmark = pytest.mark.django_db


def test_create_user_hashes_password_and_sets_role() -> None:
    user = DispatcherFactory(password="s3cret-pass")
    assert user.check_password("s3cret-pass")
    assert user.role == User.Role.DISPATCHER
    assert user.organization is not None


def test_create_user_without_organization_raises() -> None:
    with pytest.raises(ValidationError):
        User.objects.create_user(
            email="norg@example.test",
            password="x",
            full_name="No Org",
            role=User.Role.CUSTOMER,
        )


def test_create_superuser_allows_no_organization() -> None:
    su = User.objects.create_superuser(email="root@example.test", password="x")
    assert su.is_superuser
    assert su.is_staff
    assert su.organization is None
