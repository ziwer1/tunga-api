from django.core.management.base import BaseCommand

from tunga_profiles.models import Connection
from tunga_tasks.models import Application, Participation
from tunga_utils.constants import STATUS_ACCEPTED, STATUS_REJECTED, STATUS_INITIAL


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Fix payment rates based on task status
        """
        # command to run: python manage.py tunga_refactor_status_to_single_field

        # Fix connections
        Connection.objects.exclude(accepted=True).filter(responded=False).update(status=STATUS_INITIAL)
        Connection.objects.filter(accepted=True).update(status=STATUS_ACCEPTED)
        Connection.objects.filter(accepted=False, responded=True).update(status=STATUS_REJECTED)

        # Fix applications
        Application.objects.exclude(accepted=True).filter(responded=False).update(status=STATUS_INITIAL)
        Application.objects.filter(accepted=True).update(status=STATUS_ACCEPTED)
        Application.objects.filter(accepted=False, responded=True).update(status=STATUS_REJECTED)

        # Fix participation
        Participation.objects.exclude(accepted=True).filter(responded=False).update(status=STATUS_INITIAL)
        Participation.objects.filter(accepted=True).update(status=STATUS_ACCEPTED)
        Participation.objects.filter(accepted=False, responded=True).update(status=STATUS_REJECTED)
