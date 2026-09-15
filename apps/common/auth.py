from typing import Any

from rest_framework.request import Request

from apps.accounts.models import User


def current_user(request: Request) -> User:
    """Narrows request.user from AbstractBaseUser | AnonymousUser to our one
    concrete User model. Only call this after IsAuthenticated has already
    run — an anonymous request would fail the assertion."""
    user = request.user
    assert isinstance(user, User)
    return user


def ws_user(scope: Any) -> User | None:
    """Narrows a Channels consumer's scope["user"] (set by
    apps.accounts.ws_auth.JWTAuthMiddleware to either a real User or
    AnonymousUser) to our concrete User model, or None if unauthenticated —
    every consumer's connect() checks this before accepting."""
    user = scope.get("user")
    return user if isinstance(user, User) else None
