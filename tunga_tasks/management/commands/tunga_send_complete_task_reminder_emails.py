import datetime

from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db.models.aggregates import Sum
from django.db.models.expressions import Case, When, F
from django.db.models.fields import IntegerField
from django.db.models.query_utils import Q

from tunga.settings import EMAIL_SUBJECT_PREFIX, TUNGA_URL
from tunga_activity import verbs
from tunga_activity.models import ActivityReadLog
from tunga_settings.slugs import TASK_ACTIVITY_UPDATE_EMAIL
from tunga_tasks.models import Participation, Task
from tunga_tasks.notifications import send_new_task_client_receipt_email
from tunga_utils.constants import TASK_SCOPE_TASK
from tunga_utils.emails import send_mail


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Send send complete task reminders
        """
        # command to run: python manage.py tunga_send_complete_task_reminder_emails

        # Send notifications
        utc_now = datetime.datetime.utcnow()
        min_date = utc_now - relativedelta(hours=24)  # 24 hour window to complete task

        tasks = Task.objects.filter(
            scope=TASK_SCOPE_TASK, approved=False, reminded_complete_task=False, created_at__lt=min_date
        )

        for task in tasks:
            if task.is_task:
                send_new_task_client_receipt_email(task, reminder=True)
