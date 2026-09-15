import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.tests.factories import DispatcherFactory

pytestmark = pytest.mark.django_db


def test_obtain_token_includes_role_and_org_claims(api_client: APIClient) -> None:
    user = DispatcherFactory(password="testpass123")

    response = api_client.post(
        "/api/auth/token/", {"email": user.email, "password": "testpass123"}, format="json"
    )

    assert response.status_code == 200
    access = AccessToken(response.data["access"])
    assert access["role"] == "dispatcher"
    assert access["organization_id"] == str(user.organization_id)


def test_obtain_token_rejects_wrong_password(api_client: APIClient) -> None:
    user = DispatcherFactory(password="testpass123")

    response = api_client.post(
        "/api/auth/token/", {"email": user.email, "password": "wrong"}, format="json"
    )

    assert response.status_code == 401


def test_me_requires_authentication(api_client: APIClient) -> None:
    response = api_client.get("/api/me/")
    assert response.status_code == 401


def test_me_returns_current_user(api_client: APIClient) -> None:
    user = DispatcherFactory()
    api_client.force_authenticate(user=user)

    response = api_client.get("/api/me/")

    assert response.status_code == 200
    assert response.data["email"] == user.email
    assert response.data["role"] == "dispatcher"


def test_refresh_rotates_token(api_client: APIClient) -> None:
    user = DispatcherFactory(password="testpass123")
    obtain = api_client.post(
        "/api/auth/token/", {"email": user.email, "password": "testpass123"}, format="json"
    )
    refresh_token = obtain.data["refresh"]

    response = api_client.post(
        "/api/auth/token/refresh/", {"refresh": refresh_token}, format="json"
    )

    assert response.status_code == 200
    assert response.data["access"]
    assert response.data["refresh"] != refresh_token
