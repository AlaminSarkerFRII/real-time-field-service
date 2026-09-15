import factory
from factory.django import DjangoModelFactory

from apps.accounts.models import AgentProfile, Organization, User


class OrganizationFactory(DjangoModelFactory):
    class Meta:
        model = Organization

    name = factory.Sequence(lambda n: f"Org {n}")


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.test")
    full_name = factory.Faker("name")
    role = User.Role.CUSTOMER
    organization = factory.SubFactory(OrganizationFactory)

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        # Route through the real manager so passwords are hashed and the
        # organization-required guard in User.clean() actually runs — a
        # factory that bypasses both would test nothing real.
        password = kwargs.pop("password", "testpass123")
        manager = cls._get_manager(model_class)
        return manager.create_user(*args, password=password, **kwargs)


class DispatcherFactory(UserFactory):
    role = User.Role.DISPATCHER


class AgentFactory(UserFactory):
    role = User.Role.AGENT


class CustomerFactory(UserFactory):
    role = User.Role.CUSTOMER


class AgentProfileFactory(DjangoModelFactory):
    class Meta:
        model = AgentProfile

    user = factory.SubFactory(AgentFactory)
