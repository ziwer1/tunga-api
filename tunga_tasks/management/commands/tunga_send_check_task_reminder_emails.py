import datetime

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand

from tunga_tasks.models import Task


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Send send complete task reminders
        """
        # command to run: python manage.py tunga_send_check_task_reminder_emails

        # Send notifications
        utc_now = datetime.datetime.utcnow()
        min_date = utc_now - relativedelta(hours=4)  # Remind admins to check on task after 4 hours

        tasks = Task.objects.filter(
            created_at__lt=min_date, check_task_email_at__isnull=True
        )

        for task in tasks:
            pass
            # Remind admins to check on the task
