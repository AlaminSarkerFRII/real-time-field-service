from typing import Any

from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.auth import current_user
from apps.common.permissions import IsDispatcher

from . import services
from .models import Job, JobQuerySet
from .permissions import CanTransitionStatus, IsJobParticipant
from .serializers import (
    AssignSerializer,
    JobCreateSerializer,
    JobEventSerializer,
    JobSerializer,
    JobStatusSerializer,
)
from .state_machine import IllegalTransitionError


class JobViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet[Job],
):
    """No generic update/destroy — every write goes through a named action
    (assign, status) backed by apps.jobs.services, per docs/architecture.md
    #5: "REST is the only thing that writes... one code path, tested once."
    """

    serializer_class = JobSerializer

    def get_queryset(self) -> JobQuerySet:
        return (
            Job.objects.select_related("customer", "agent", "organization")
            .visible_to(current_user(self.request))
        )

    def get_permissions(self) -> list[BasePermission]:
        if self.action in ("create", "assign"):
            classes: list[type[BasePermission]] = [IsAuthenticated, IsDispatcher]
        elif self.action == "status":
            classes = [IsAuthenticated, CanTransitionStatus]
        elif self.action in ("retrieve", "events"):
            classes = [IsAuthenticated, IsJobParticipant]
        else:
            classes = [IsAuthenticated]
        return [cls() for cls in classes]

    def get_serializer_class(self) -> type[Any]:
        if self.action == "create":
            return JobCreateSerializer
        return JobSerializer

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job = serializer.save(organization=current_user(request).organization)
        return Response(JobSerializer(job).data, status=201)

    @action(detail=True, methods=["post"])
    def assign(self, request: Request, pk: str | None = None) -> Response:
        job = self.get_object()
        serializer = AssignSerializer(data=request.data, context={"job": job})
        serializer.is_valid(raise_exception=True)
        try:
            updated = services.assign(
                job=job, agent=serializer.validated_data["agent"], actor=current_user(request)
            )
        except IllegalTransitionError as exc:
            raise DRFValidationError({"detail": str(exc)}) from exc
        return Response(JobSerializer(updated).data)

    @action(detail=True, methods=["patch"])
    def status(self, request: Request, pk: str | None = None) -> Response:
        job = self.get_object()
        serializer = JobStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            updated = services.transition(
                job=job,
                to_status=serializer.validated_data["to_status"],
                actor=current_user(request),
            )
        except IllegalTransitionError as exc:
            raise DRFValidationError({"detail": str(exc)}) from exc
        return Response(JobSerializer(updated).data)

    @action(detail=True, methods=["get"])
    def events(self, request: Request, pk: str | None = None) -> Response:
        # Unpaginated: one job's audit trail is a handful of rows, never
        # unbounded — unlike /messages/, which the REST contract paginates.
        job = self.get_object()
        events = job.events.select_related("actor")
        return Response(JobEventSerializer(events, many=True).data)
