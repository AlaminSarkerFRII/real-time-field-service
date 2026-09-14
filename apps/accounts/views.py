from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import User
from .serializers import FieldSyncTokenObtainPairSerializer, MeSerializer


class TokenObtainPairWithClaimsView(TokenObtainPairView):
    # Upstream types this attribute as None on the base class; overriding
    # with a concrete serializer is the documented way to use it.
    serializer_class = FieldSyncTokenObtainPairSerializer  # type: ignore[assignment]


class MeView(RetrieveAPIView[User]):
    serializer_class = MeSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self) -> User:
        user = self.request.user
        assert isinstance(user, User)
        return user
