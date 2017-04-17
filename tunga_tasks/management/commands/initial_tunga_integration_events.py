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
            # Git Events
            {'id': slugs.EVENT_PUSH, 'name': 'Push events'},
            {'id': slugs.EVENT_BRANCH, 'name': 'Branch creation and deletion'},
            {'id': slugs.EVENT_TAG, 'name': 'Tag creation and deletion'},
            {'id': slugs.EVENT_COMMIT_COMMENT, 'name': 'Commit comments'},
            {'id': slugs.EVENT_PULL_REQUEST, 'name': 'Pull requests'},
            {'id': slugs.EVENT_PULL_REQUEST_COMMENT, 'name': 'Pull request comments'},
            {'id': slugs.EVENT_ISSUE, 'name': 'Issue creation and modification'},
            {'id': slugs.EVENT_ISSUE_COMMENT, 'name': 'Issue comments'},
            {'id': slugs.EVENT_WIKI, 'name': 'Wiki updates'},

            # Task Activity
            {'id': slugs.EVENT_COMMUNICATION, 'name': 'Comments and files uploads'},
            {'id': slugs.EVENT_APPLICATION, 'name': 'Developer applications and invitations'},
            {'id': slugs.EVENT_PROGRESS, 'name': 'Progress reports and milestone updates'}
        ]

        for event in events:
            IntegrationEvent.objects.update_or_create(id=event['id'], defaults=event)

        print("%s integration events added or edited" % len(events))
