from typing import Any

from rest_framework import serializers

from apps.accounts.models import User

from .models import Job, JobEvent
from .state_machine import JobStatus


class JobSerializer(serializers.ModelSerializer[Job]):
    """Read/output representation — every action returns this, but nothing
    writes through it. Writes go through JobCreateSerializer or the
    assign/status actions, which call apps.jobs.services directly."""

    customer_email = serializers.EmailField(source="customer.email", read_only=True)
    agent_email = serializers.EmailField(source="agent.email", read_only=True, allow_null=True)

    class Meta:
        model = Job
        fields = [
            "id",
            "reference",
            "status",
            "priority",
            "address",
            "lat",
            "lng",
            "scheduled_for",
            "customer",
            "customer_email",
            "agent",
            "agent_email",
            "organization",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "reference",
            "status",
            "customer",
            "agent",
            "organization",
            "created_at",
            "updated_at",
        ]


class JobCreateSerializer(serializers.ModelSerializer[Job]):
    customer = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=User.Role.CUSTOMER)
    )

    class Meta:
        model = Job
        fields = ["customer", "address", "lat", "lng", "scheduled_for", "priority"]

    def validate_customer(self, customer: User) -> User:
        request_user: User = self.context["request"].user
        if customer.organization_id != request_user.organization_id:
            raise serializers.ValidationError("Customer must belong to your organization.")
        return customer


class AssignSerializer(serializers.Serializer[Any]):
    agent = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role=User.Role.AGENT))

    def validate_agent(self, agent: User) -> User:
        job: Job = self.context["job"]
        if agent.organization_id != job.organization_id:
            raise serializers.ValidationError(
                "Agent must belong to the same organization as the job."
            )
        return agent


class JobStatusSerializer(serializers.Serializer[Any]):
    to_status = serializers.ChoiceField(choices=JobStatus.choices)


class JobEventSerializer(serializers.ModelSerializer[JobEvent]):
    actor_email = serializers.EmailField(source="actor.email", read_only=True)

    class Meta:
        model = JobEvent
        fields = ["id", "from_status", "to_status", "actor", "actor_email", "created_at"]
        read_only_fields = fields
