from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import Token

from .models import User


class FieldSyncTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Adds role and organization to the JWT so the frontend can route on login
    without a second round trip to /api/me/."""

    @classmethod
    def get_token(cls, user: User) -> Token:  # type: ignore[override]
        # Narrowed from simplejwt's AuthUser TypeVar to our one concrete User
        # model — this app has exactly one, so the narrowing is intentional.
        token = super().get_token(user)
        token["role"] = user.role
        token["organization_id"] = str(user.organization_id) if user.organization_id else None
        return token


class MeSerializer(serializers.ModelSerializer[User]):
    class Meta:
        model = User
        fields = ["id", "email", "full_name", "role", "organization"]
        read_only_fields = fields
