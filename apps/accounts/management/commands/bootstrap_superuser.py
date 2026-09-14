import os
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Idempotently create the platform superuser from DJANGO_SUPERUSER_* env vars."

    def handle(self, *args: Any, **options: Any) -> None:
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
        full_name = os.environ.get("DJANGO_SUPERUSER_FULL_NAME", "Platform Admin")

        if not email or not password:
            raise CommandError(
                "DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD must be set (see .env)."
            )

        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.WARNING(f"Superuser {email} already exists, skipping."))
            return

        User.objects.create_superuser(email=email, password=password, full_name=full_name)
        self.stdout.write(self.style.SUCCESS(f"Created superuser {email}."))
