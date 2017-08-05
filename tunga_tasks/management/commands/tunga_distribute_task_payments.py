import datetime

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand

from tunga_tasks.models import Task
from tunga_tasks.tasks import distribute_task_payment


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Distribute task payments.
        """
        # command to run: python manage.py tunga_distribute_task_payments

        utc_now = datetime.datetime.utcnow()
        min_date = utc_now - relativedelta(minutes=10)  # 10 minute window to read new messages

        # Distribute payments for tasks which where paid at least 10 mins ago
        tasks = Task.objects.filter(closed=True, paid=True, pay_distributed=False, paid_at__lte=min_date)
        for task in tasks:
            distribute_task_payment.delay(task.id)
