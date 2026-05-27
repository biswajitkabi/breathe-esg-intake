from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
import os

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        User = get_user_model()

        username = os.getenv("DJANGO_SUPERUSER_USERNAME")
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD")

        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(
                username=username,
                password=password
            )

            self.stdout.write(
                self.style.SUCCESS("Superuser created")
            )
        else:
            self.stdout.write(
                self.style.WARNING("Superuser already exists")
            )