import datetime

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand

from tunga_tasks.emails import send_progress_event_reminder_email
from tunga_tasks.models import Task, ProgressEvent
from tunga_tasks.tasks import initialize_task_progress_events


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Update periodic update events and send notifications for upcoming update events.
        """
        # command to run: python manage.py tunga_manage_task_progress

        tasks = Task.objects.filter(closed=False)
        for task in tasks:
            # Creates the next periodic events and reconciles submit events if necessary
            initialize_task_progress_events(task)

        min_date = datetime.datetime.utcnow()
        max_date = min_date + relativedelta(hours=24)

        events = ProgressEvent.objects.filter(
            task__closed=False, due_at__range=[min_date, max_date], last_reminder_at__isnull=True
        )
        for event in events:
            send_progress_event_reminder_email(event.id)
