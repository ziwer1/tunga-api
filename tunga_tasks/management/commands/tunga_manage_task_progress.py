import datetime

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand
from django.db.models.query_utils import Q

from tunga_tasks.notifications.generic import remind_progress_event, notify_missed_progress_event
from tunga_tasks.models import Task, ProgressEvent
from tunga_tasks.tasks import initialize_task_progress_events


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Update periodic update events and send notifications for upcoming update events.
        """
        # command to run: python manage.py tunga_manage_task_progress

        # Periodic updates will continue to be scheduled for unclosed tasks for up to a week past their deadlines
        min_deadline = datetime.datetime.utcnow() - relativedelta(days=7)
        tasks = Task.objects.filter(Q(deadline__isnull=True) | Q(deadline__gte=min_deadline), closed=False)
        for task in tasks:
            # Creates the next periodic events and reconciles submit events if necessary
            initialize_task_progress_events(task)

        right_now = datetime.datetime.utcnow()
        future_by_8_hours = right_now + relativedelta(hours=8)
        past_by_24_hours = right_now - relativedelta(hours=24)
        past_by_48_hours = right_now - relativedelta(hours=48)

        # Send reminders for tasks updates due in the current 24 hr period
        events = ProgressEvent.objects.filter(
            task__closed=False, due_at__range=[right_now, future_by_8_hours], last_reminder_at__isnull=True
        )
        for event in events:
            remind_progress_event(event.id)

        # Notify Tunga of missed updates (limit to events due in last 48 hours, prevents spam from very old tasks)
        missed_events = ProgressEvent.objects.filter(
            due_at__range=[past_by_48_hours, past_by_24_hours], missed_notification_at__isnull=True
        )
        for event in missed_events:
            notify_missed_progress_event(event.id)
