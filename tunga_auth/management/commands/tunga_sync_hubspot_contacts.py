from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from tunga_auth.tasks import sync_hubspot_contact
from tunga_utils.constants import USER_TYPE_PROJECT_OWNER


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Sync client contacts with HubSpot.
        """
        # command to run: python manage.py tunga_sync_hubspot_contacts

        clients = get_user_model().objects.filter(type=USER_TYPE_PROJECT_OWNER)
        for client in clients:
            # Sync client contact with HubSpot
            sync_hubspot_contact(client)
