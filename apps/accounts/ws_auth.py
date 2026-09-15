from typing import Any
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

from .models import User


@database_sync_to_async
def _get_user_from_token(token: str) -> User | AnonymousUser:
    try:
        # simplejwt's own type hint for this parameter (Optional["Token"]) is
        # wrong — it's the raw encoded JWT string, exactly as their own docs
        # use it; AccessToken.__init__ never actually receives a Token.
        validated = AccessToken(token)  # type: ignore[arg-type]
        return User.objects.get(pk=validated["user_id"])
    except (TokenError, InvalidToken, User.DoesNotExist):
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """Authenticates a WebSocket connection from ?token=<access-jwt> in the
    query string — the WS equivalent of the Authorization header on REST,
    per docs/architecture.md #6. An invalid or missing token leaves
    scope["user"] anonymous; each consumer's connect() rejects that."""

    async def __call__(self, scope: Any, receive: Any, send: Any) -> Any:
        query_string = scope.get("query_string", b"").decode()
        token = parse_qs(query_string).get("token", [None])[0]
        scope["user"] = await _get_user_from_token(token) if token else AnonymousUser()
        return await super().__call__(scope, receive, send)
