from typing import Any

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.accounts.models import User
from apps.accounts.services import record_location
from apps.common.auth import ws_user
from apps.realtime.groups import job_group, org_group, user_group

from .models import Job


class DispatchConsumer(AsyncJsonWebsocketConsumer):
    """/ws/dispatch/ — one org-wide feed for the dispatcher's live map and
    job list. Never receives messages from the client, per
    docs/architecture.md #6."""

    async def connect(self) -> None:
        user = ws_user(self.scope)
        if user is None or user.role != User.Role.DISPATCHER:
            await self.close(code=4003)
            return
        self.group_name = org_group(user.organization_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code: int) -> None:
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def agent_location(self, event: dict[str, Any]) -> None:
        await self.send_json(event)

    async def job_update(self, event: dict[str, Any]) -> None:
        await self.send_json(event)


class AgentConsumer(AsyncJsonWebsocketConsumer):
    """/ws/agent/ — the field agent's socket: streams location.ping in,
    receives job.update/notify pushed to their org/personal groups. Groups
    per docs/architecture.md #6: org.<org_id> and user.<id>."""

    async def connect(self) -> None:
        user = ws_user(self.scope)
        if user is None or user.role != User.Role.AGENT:
            await self.close(code=4003)
            return
        self.org_group_name = org_group(user.organization_id)
        self.user_group_name = user_group(user.id)
        await self.channel_layer.group_add(self.org_group_name, self.channel_name)
        await self.channel_layer.group_add(self.user_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code: int) -> None:
        if hasattr(self, "org_group_name"):
            await self.channel_layer.group_discard(self.org_group_name, self.channel_name)
            await self.channel_layer.group_discard(self.user_group_name, self.channel_name)

    async def receive_json(self, content: dict[str, Any], **kwargs: Any) -> None:
        if content.get("type") != "location.ping":
            return
        user = ws_user(self.scope)
        assert user is not None  # connect() already rejected anonymous scopes
        profile = await database_sync_to_async(record_location)(
            agent=user, lat=content["lat"], lng=content["lng"]
        )
        assert profile.last_ping_at is not None
        await self.channel_layer.group_send(
            self.org_group_name,
            {
                "type": "agent.location",
                "agent_id": str(user.id),
                "lat": str(profile.last_lat),
                "lng": str(profile.last_lng),
                "at": profile.last_ping_at.isoformat(),
            },
        )

    async def agent_location(self, event: dict[str, Any]) -> None:
        await self.send_json(event)

    async def job_update(self, event: dict[str, Any]) -> None:
        await self.send_json(event)

    async def notify(self, event: dict[str, Any]) -> None:
        await self.send_json(event)


class JobConsumer(AsyncJsonWebsocketConsumer):
    """/ws/jobs/<job_id>/ — one job's room: status updates today, chat once
    apps.chat's ChatConsumerMixin is composed in (docs/repo-structure.md)."""

    async def connect(self) -> None:
        user = ws_user(self.scope)
        job_id = self.scope["url_route"]["kwargs"]["job_id"]
        job = await self._get_job_if_participant(user, job_id)
        if job is None:
            await self.close(code=4004)
            return
        self.group_name = job_group(job_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code: int) -> None:
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def job_update(self, event: dict[str, Any]) -> None:
        await self.send_json(event)

    @database_sync_to_async
    def _get_job_if_participant(self, user: User | None, job_id: str) -> Job | None:
        if user is None:
            return None
        try:
            return Job.objects.visible_to(user).get(pk=job_id)
        except (Job.DoesNotExist, ValueError):
            return None
