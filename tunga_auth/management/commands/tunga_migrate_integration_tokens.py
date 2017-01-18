from django.core.management.base import BaseCommand

from tunga_tasks.models import Integration
from tunga_tasks.utils import save_integration_tokens


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Sync client contacts with HubSpot.
        """
        # command to run: python manage.py tunga_migrate_integration_tokens

        integrations = Integration.objects.filter()
        for integration in integrations:
            # Sync client contact with Integration
            save_integration_tokens(integration.task.user, integration.task_id, integration.provider)
