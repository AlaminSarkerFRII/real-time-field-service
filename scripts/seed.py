#!/usr/bin/env python
"""Seed a demo organization with one user per role and a job in every status
— for local dev/demo, never production. Idempotent: safe to re-run.

Jobs are driven through apps.jobs.services, not created directly in their
final status, so the audit trail (JobEvent) and notifications this script
produces are the same ones the real API would produce.

Usage: python scripts/seed.py
"""

import os
import sys
from pathlib import Path

import django

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

from apps.accounts.models import AgentProfile, Organization, User  # noqa: E402
from apps.jobs import services  # noqa: E402
from apps.jobs.models import Job  # noqa: E402
from apps.jobs.state_machine import JobStatus  # noqa: E402

ORG_NAME = "Riverside Plumbing & HVAC"
DEMO_PASSWORD = "demo-pass-123"  # seed-only, never a real credential


def get_or_create_user(email: str, **fields: object) -> tuple[User, bool]:
    try:
        return User.objects.get(email=email), False
    except User.DoesNotExist:
        return User.objects.create_user(email=email, password=DEMO_PASSWORD, **fields), True


def main() -> None:
    org, org_created = Organization.objects.get_or_create(
        name=ORG_NAME, defaults={"timezone": "America/New_York"}
    )
    print(f"{'Created' if org_created else 'Using existing'} organization: {org.name}")

    dispatcher, _ = get_or_create_user(
        "dispatcher@riverside.demo",
        full_name="Dana Dispatcher",
        role=User.Role.DISPATCHER,
        organization=org,
    )
    agent, _ = get_or_create_user(
        "agent@riverside.demo", full_name="Alex Agent", role=User.Role.AGENT, organization=org
    )
    AgentProfile.objects.get_or_create(user=agent, defaults={"skills": ["plumbing", "hvac"]})
    customer, _ = get_or_create_user(
        "customer@riverside.demo",
        full_name="Cory Customer",
        role=User.Role.CUSTOMER,
        organization=org,
    )
    print(
        f"Users ready (password: {DEMO_PASSWORD}): "
        f"{dispatcher.email} · {agent.email} · {customer.email}"
    )

    if Job.objects.filter(organization=org).exists():
        print("Jobs already seeded for this organization — leaving them as is.")
        return

    new_job = Job.objects.create(organization=org, customer=customer, address="12 Willow St")

    assigned_job = Job.objects.create(
        organization=org, customer=customer, address="48 Maple Ave", priority=Job.Priority.URGENT
    )
    assigned_job = services.assign(job=assigned_job, agent=agent, actor=dispatcher)

    en_route_job = Job.objects.create(organization=org, customer=customer, address="9 Oak Dr")
    en_route_job = services.assign(job=en_route_job, agent=agent, actor=dispatcher)
    en_route_job = services.transition(job=en_route_job, to_status=JobStatus.EN_ROUTE, actor=agent)

    on_site_job = Job.objects.create(organization=org, customer=customer, address="200 Birch Blvd")
    on_site_job = services.assign(job=on_site_job, agent=agent, actor=dispatcher)
    on_site_job = services.transition(job=on_site_job, to_status=JobStatus.EN_ROUTE, actor=agent)
    on_site_job = services.transition(job=on_site_job, to_status=JobStatus.ON_SITE, actor=agent)

    completed_job = Job.objects.create(organization=org, customer=customer, address="77 Cedar Ct")
    completed_job = services.assign(job=completed_job, agent=agent, actor=dispatcher)
    completed_job = services.transition(
        job=completed_job, to_status=JobStatus.EN_ROUTE, actor=agent
    )
    completed_job = services.transition(job=completed_job, to_status=JobStatus.ON_SITE, actor=agent)
    completed_job = services.transition(
        job=completed_job, to_status=JobStatus.COMPLETED, actor=agent
    )

    cancelled_job = Job.objects.create(organization=org, customer=customer, address="5 Pine Ln")
    cancelled_job = services.assign(job=cancelled_job, agent=agent, actor=dispatcher)
    cancelled_job = services.transition(
        job=cancelled_job, to_status=JobStatus.CANCELLED, actor=dispatcher
    )

    for job in (new_job, assigned_job, en_route_job, on_site_job, completed_job, cancelled_job):
        print(f"  {job.reference}  {job.status:<10}  {job.address}")
    print("Seeded 6 jobs, one per status.")


if __name__ == "__main__":
    main()
