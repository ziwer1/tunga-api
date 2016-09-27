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

            # Chat Events
            {'id': slugs.EVENT_COMMENT, 'name': 'Comments'},
            {'id': slugs.EVENT_UPLOAD, 'name': 'Uploads'},

            # Task Activity
            {'id': slugs.EVENT_TASK_TASK_APPLY_OR_ACCEPT, 'name': 'Developer applies or accepts task'},
            {'id': slugs.EVENT_PROGRESS_REPORT, 'name': 'Progress reports'}
        ]

        for event in events:
            IntegrationEvent.objects.update_or_create(id=event['id'], defaults=event)

        print "%s integration events added or edited" % len(events)
