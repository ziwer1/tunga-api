import datetime

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand
from django.db.models.query_utils import Q

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

        welcome_tasks = Task.objects.exclude(user__tasks_created__last_drip_mail_at__gt=past_by_24_hrs).filter(
            Q(last_drip_mail__isnull=True) | Q(last_drip_mail=''),
            source=TASK_SOURCE_NEW_USER,
            approved=False,
            created_at__range=[past_by_48_hrs, past_by_15_mins]
        )

        for welcome_task in welcome_tasks:
            notify_new_task_client_drip_one(welcome_task)

        hiring_tasks = Task.objects.exclude(user__tasks_created__last_drip_mail_at__gt=past_by_24_hrs).filter(
            source=TASK_SOURCE_NEW_USER,
            approved=False,
            last_drip_mail='welcome',
            last_drip_mail__lt=past_by_24_hrs
        )

        for hiring_task in hiring_tasks:
            notify_new_task_client_drip_one(hiring_task, template='hiring')
