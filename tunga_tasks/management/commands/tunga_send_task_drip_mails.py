import datetime

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand

from tunga_tasks.models import Task
from tunga_tasks.notifications.email import notify_new_task_client_drip_one
from tunga_utils.constants import TASK_SOURCE_NEW_USER


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Send send complete task reminders
        """
        # command to run: python manage.py tunga_send_task_drip_mails

        # Send notifications
        utc_now = datetime.datetime.utcnow()
        past_by_48_hrs = utc_now - relativedelta(hours=48)
        past_by_24_hrs = utc_now - relativedelta(hours=24)
        past_by_15_mins = utc_now - relativedelta(minutes=15)

        tasks = Task.objects.filter(
            source=TASK_SOURCE_NEW_USER,
            approved=False,
            last_drip_mail__isnull=True,
            created_at__range=[past_by_48_hrs, past_by_15_mins]
        )

        for task in tasks:
            notify_new_task_client_drip_one(task)

        tasks = Task.objects.filter(
            source=TASK_SOURCE_NEW_USER,
            approved=False,
            last_drip_mail='welcome',
            last_drip_mail__lt=past_by_24_hrs
        )

        for task in tasks:
            notify_new_task_client_drip_one(task, template='hiring')
