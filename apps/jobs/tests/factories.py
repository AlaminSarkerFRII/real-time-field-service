import factory
from factory.django import DjangoModelFactory

from apps.accounts.tests.factories import CustomerFactory, OrganizationFactory
from apps.jobs.models import Job


class JobFactory(DjangoModelFactory):
    class Meta:
        model = Job

    organization = factory.SubFactory(OrganizationFactory)
    customer = factory.SubFactory(
        CustomerFactory, organization=factory.SelfAttribute("..organization")
    )
    address = factory.Faker("street_address")
