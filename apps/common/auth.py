from rest_framework.request import Request

from apps.accounts.models import User


def current_user(request: Request) -> User:
    """Narrows request.user from AbstractBaseUser | AnonymousUser to our one
    concrete User model. Only call this after IsAuthenticated has already
    run — an anonymous request would fail the assertion."""
    user = request.user
    assert isinstance(user, User)
    return user
