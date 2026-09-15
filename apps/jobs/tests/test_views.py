import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import AgentFactory, CustomerFactory, DispatcherFactory
from apps.jobs import services
from apps.jobs.models import Job
from apps.jobs.state_machine import JobStatus
from apps.jobs.tests.factories import JobFactory

pytestmark = pytest.mark.django_db


def test_dispatcher_can_create_job(api_client: APIClient) -> None:
    dispatcher = DispatcherFactory()
    customer = CustomerFactory(organization=dispatcher.organization)
    api_client.force_authenticate(user=dispatcher)

    response = api_client.post(
        "/api/jobs/", {"customer": str(customer.id), "address": "1 Test St"}, format="json"
    )

    assert response.status_code == 201, response.data
    assert response.data["status"] == JobStatus.NEW
    assert Job.objects.filter(pk=response.data["id"]).exists()


def test_agent_cannot_create_job(api_client: APIClient) -> None:
    agent = AgentFactory()
    api_client.force_authenticate(user=agent)

    response = api_client.post("/api/jobs/", {}, format="json")

    assert response.status_code == 403


def test_create_job_rejects_customer_from_another_org(api_client: APIClient) -> None:
    dispatcher = DispatcherFactory()
    other_customer = CustomerFactory()  # different org
    api_client.force_authenticate(user=dispatcher)

    response = api_client.post(
        "/api/jobs/",
        {"customer": str(other_customer.id), "address": "1 Test St"},
        format="json",
    )

    assert response.status_code == 400


def test_list_is_scoped_by_role(api_client: APIClient) -> None:
    dispatcher = DispatcherFactory()
    org = dispatcher.organization
    agent = AgentFactory(organization=org)
    other_agent = AgentFactory(organization=org)
    customer = CustomerFactory(organization=org)

    JobFactory(organization=org, customer=customer, agent=agent)
    JobFactory(organization=org, customer=customer, agent=other_agent)
    JobFactory()  # different org entirely

    api_client.force_authenticate(user=dispatcher)
    assert api_client.get("/api/jobs/").data["count"] == 2

    api_client.force_authenticate(user=agent)
    assert api_client.get("/api/jobs/").data["count"] == 1

    api_client.force_authenticate(user=customer)
    assert api_client.get("/api/jobs/").data["count"] == 2


def test_dispatcher_from_another_org_gets_404_not_403(api_client: APIClient) -> None:
    job = JobFactory()
    outsider = DispatcherFactory()  # different org
    api_client.force_authenticate(user=outsider)

    detail = api_client.get(f"/api/jobs/{job.id}/")
    assert detail.status_code == 404

    assign = api_client.post(
        f"/api/jobs/{job.id}/assign/", {"agent": str(outsider.id)}, format="json"
    )
    assert assign.status_code == 404


def test_dispatcher_can_assign_agent(api_client: APIClient) -> None:
    job = JobFactory()
    dispatcher = DispatcherFactory(organization=job.organization)
    agent = AgentFactory(organization=job.organization)
    api_client.force_authenticate(user=dispatcher)

    response = api_client.post(
        f"/api/jobs/{job.id}/assign/", {"agent": str(agent.id)}, format="json"
    )

    assert response.status_code == 200, response.data
    assert response.data["status"] == JobStatus.ASSIGNED
    assert response.data["agent"] == agent.id


def test_assign_rejects_agent_from_another_org(api_client: APIClient) -> None:
    job = JobFactory()
    dispatcher = DispatcherFactory(organization=job.organization)
    outside_agent = AgentFactory()  # different org
    api_client.force_authenticate(user=dispatcher)

    response = api_client.post(
        f"/api/jobs/{job.id}/assign/", {"agent": str(outside_agent.id)}, format="json"
    )

    assert response.status_code == 400


def test_customer_cannot_change_status(api_client: APIClient) -> None:
    job = JobFactory()
    services.assign(
        job=job,
        agent=AgentFactory(organization=job.organization),
        actor=DispatcherFactory(organization=job.organization),
    )
    api_client.force_authenticate(user=job.customer)

    response = api_client.patch(
        f"/api/jobs/{job.id}/status/", {"to_status": JobStatus.EN_ROUTE}, format="json"
    )

    assert response.status_code == 403


def test_agent_can_walk_status_through_full_lifecycle(api_client: APIClient) -> None:
    job = JobFactory()
    dispatcher = DispatcherFactory(organization=job.organization)
    agent = AgentFactory(organization=job.organization)
    services.assign(job=job, agent=agent, actor=dispatcher)
    api_client.force_authenticate(user=agent)

    for to_status in (JobStatus.EN_ROUTE, JobStatus.ON_SITE, JobStatus.COMPLETED):
        response = api_client.patch(
            f"/api/jobs/{job.id}/status/", {"to_status": to_status}, format="json"
        )
        assert response.status_code == 200, response.data
        assert response.data["status"] == to_status


def test_illegal_status_transition_returns_400(api_client: APIClient) -> None:
    job = JobFactory()
    dispatcher = DispatcherFactory(organization=job.organization)
    agent = AgentFactory(organization=job.organization)
    services.assign(job=job, agent=agent, actor=dispatcher)
    api_client.force_authenticate(user=agent)

    response = api_client.patch(
        f"/api/jobs/{job.id}/status/", {"to_status": JobStatus.COMPLETED}, format="json"
    )

    assert response.status_code == 400


def test_events_returns_audit_trail_in_order(api_client: APIClient) -> None:
    job = JobFactory()
    dispatcher = DispatcherFactory(organization=job.organization)
    agent = AgentFactory(organization=job.organization)
    services.assign(job=job, agent=agent, actor=dispatcher)
    services.transition(job=job, to_status=JobStatus.EN_ROUTE, actor=agent)
    api_client.force_authenticate(user=dispatcher)

    response = api_client.get(f"/api/jobs/{job.id}/events/")

    assert response.status_code == 200
    assert [e["to_status"] for e in response.data] == [JobStatus.ASSIGNED, JobStatus.EN_ROUTE]
