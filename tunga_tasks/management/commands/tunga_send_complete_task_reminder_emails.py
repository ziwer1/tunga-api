import datetime

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand

from tunga_tasks.models import Task
from tunga_tasks.notifications.email import notify_new_task_client_receipt_email
from tunga_utils.constants import TASK_SCOPE_TASK, TASK_SOURCE_NEW_USER


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Send send complete task reminders
        """
        # command to run: python manage.py tunga_send_complete_task_reminder_emails

        # Send notifications
        utc_now = datetime.datetime.utcnow()
        min_date = utc_now - relativedelta(hours=24)  # 24 hour window to complete task

        tasks = Task.objects.exclude(source=TASK_SOURCE_NEW_USER).filter(
            scope=TASK_SCOPE_TASK, approved=False, reminded_complete_task=False, created_at__lt=min_date
        )

        for task in tasks:
            if task.is_task:
                notify_new_task_client_receipt_email(task, reminder=True)
