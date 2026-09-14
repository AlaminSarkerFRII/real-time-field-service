from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import MeView, TokenObtainPairWithClaimsView

urlpatterns = [
    path("auth/token/", TokenObtainPairWithClaimsView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("me/", MeView.as_view(), name="me"),
]
