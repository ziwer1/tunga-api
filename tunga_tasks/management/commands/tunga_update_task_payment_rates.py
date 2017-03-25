import datetime

from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from decimal import Decimal
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
from tunga_utils.emails import send_mail


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Fix payment rates based on task status
        """
        # command to run: python manage.py tunga_update_task_payment_rates.py

        # Initialize missing logs
        tasks = Task.objects.filter(closed=False)
        for task in tasks:
            active_participants = task.participation_set.filter(accepted=True).count()
            print task.id, active_participants
            if not active_participants:
                task.dev_rate = Decimal(19)
                task.pm_rate = Decimal(39)
                task.pm_time_percentage = Decimal(15)
                task.tunga_percentage_dev = Decimal('34.21')
                task.tunga_percentage_pm = Decimal('48.71')
                task.save()
