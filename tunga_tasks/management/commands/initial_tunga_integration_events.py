from django.core.management.base import BaseCommand

from tunga_tasks import slugs
from tunga_tasks.models import IntegrationEvent


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Creates default integration events.
        """
        # command to run: python manage.py initial_tunga_integration_events

        events = [
            {'id': slugs.PUSH, 'name': 'Push events'},
            {'id': slugs.BRANCH, 'name': 'Branch creation and deletion'},
            {'id': slugs.TAG, 'name': 'Tag creation and deletion'},
            {'id': slugs.COMMIT_COMMENT, 'name': 'Commit comments'},
            {'id': slugs.PULL_REQUEST, 'name': 'Pull requests'},
            {'id': slugs.PULL_REQUEST_COMMENT, 'name': 'Pull request comments'},
            {'id': slugs.ISSUE, 'name': 'Issue creation and modification'},
            {'id': slugs.ISSUE_COMMENT, 'name': 'Issue comments'},
            {'id': slugs.WIKI, 'name': 'Wiki updates'},
        ]

        for event in events:
            IntegrationEvent.objects.update_or_create(id=event['id'], defaults=event)

        print "%s integration events added or edited" % len(events)
