import pytest
from channels.db import database_sync_to_async
from channels.routing import URLRouter

# channels.testing unconditionally imports ChannelsLiveServerTestCase, which
# requires daphne — a dev/test-only dependency even though uvicorn is the
# actual server (tech-stack.md D2/D3); Channels' testing API needs it to
# import at all, whichever submodule is requested.
from channels.testing import WebsocketCommunicator
from django.urls import path
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import AgentProfile
from apps.accounts.tests.factories import AgentFactory, CustomerFactory, DispatcherFactory
from apps.accounts.ws_auth import JWTAuthMiddleware
from apps.jobs import services
from apps.jobs.tests.factories import JobFactory

from ..consumers import AgentConsumer, DispatchConsumer, JobConsumer

application = JWTAuthMiddleware(
    URLRouter(
        [
            path("ws/dispatch/", DispatchConsumer.as_asgi()),
            path("ws/agent/", AgentConsumer.as_asgi()),
            path("ws/jobs/<uuid:job_id>/", JobConsumer.as_asgi()),
        ]
    )
)

pytestmark = pytest.mark.django_db(transaction=True)


@database_sync_to_async
def token_for(user) -> str:
    return str(RefreshToken.for_user(user).access_token)


async def test_agent_consumer_rejects_missing_token() -> None:
    communicator = WebsocketCommunicator(application, "/ws/agent/")
    connected, _ = await communicator.connect()
    assert connected is False
    await communicator.disconnect()


async def test_dispatch_consumer_rejects_non_dispatcher() -> None:
    agent = await database_sync_to_async(AgentFactory)()
    token = await token_for(agent)
    communicator = WebsocketCommunicator(application, f"/ws/dispatch/?token={token}")
    connected, _ = await communicator.connect()
    assert connected is False
    await communicator.disconnect()


async def test_job_consumer_rejects_non_participant() -> None:
    job = await database_sync_to_async(JobFactory)()
    outsider = await database_sync_to_async(DispatcherFactory)()  # different org
    token = await token_for(outsider)
    communicator = WebsocketCommunicator(application, f"/ws/jobs/{job.id}/?token={token}")
    connected, _ = await communicator.connect()
    assert connected is False
    await communicator.disconnect()


async def test_agent_location_ping_updates_profile_and_broadcasts_to_dispatcher() -> None:
    dispatcher = await database_sync_to_async(DispatcherFactory)()
    agent = await database_sync_to_async(AgentFactory)(organization=dispatcher.organization)
    dispatch_token = await token_for(dispatcher)
    agent_token = await token_for(agent)

    dispatch_comm = WebsocketCommunicator(application, f"/ws/dispatch/?token={dispatch_token}")
    connected, _ = await dispatch_comm.connect()
    assert connected is True

    agent_comm = WebsocketCommunicator(application, f"/ws/agent/?token={agent_token}")
    connected, _ = await agent_comm.connect()
    assert connected is True

    await agent_comm.send_json_to({"type": "location.ping", "lat": 40.0, "lng": -73.0})

    event = await dispatch_comm.receive_json_from(timeout=5)
    assert event["type"] == "agent.location"
    assert event["agent_id"] == str(agent.id)
    assert float(event["lat"]) == 40.0

    profile = await database_sync_to_async(AgentProfile.objects.get)(user=agent)
    assert profile.status == AgentProfile.Status.ONLINE
    assert profile.last_ping_at is not None

    await dispatch_comm.disconnect()
    await agent_comm.disconnect()


async def test_status_transition_broadcasts_to_dispatch_and_job_room() -> None:
    job = await database_sync_to_async(JobFactory)()
    dispatcher = await database_sync_to_async(DispatcherFactory)(organization=job.organization)
    agent = await database_sync_to_async(AgentFactory)(organization=job.organization)
    dispatch_token = await token_for(dispatcher)
    customer_token = await token_for(job.customer)

    dispatch_comm = WebsocketCommunicator(application, f"/ws/dispatch/?token={dispatch_token}")
    assert (await dispatch_comm.connect())[0] is True

    job_comm = WebsocketCommunicator(application, f"/ws/jobs/{job.id}/?token={customer_token}")
    assert (await job_comm.connect())[0] is True

    await database_sync_to_async(services.assign)(job=job, agent=agent, actor=dispatcher)

    d_event = await dispatch_comm.receive_json_from(timeout=5)
    j_event = await job_comm.receive_json_from(timeout=5)
    assert d_event["type"] == "job.update" and d_event["status"] == "assigned"
    assert j_event["type"] == "job.update" and j_event["status"] == "assigned"

    await dispatch_comm.disconnect()
    await job_comm.disconnect()


async def test_customer_cannot_open_dispatch_or_agent_sockets() -> None:
    customer = await database_sync_to_async(CustomerFactory)()
    token = await token_for(customer)
    for path_ in ("/ws/dispatch/", "/ws/agent/"):
        communicator = WebsocketCommunicator(application, f"{path_}?token={token}")
        connected, _ = await communicator.connect()
        assert connected is False
        await communicator.disconnect()
