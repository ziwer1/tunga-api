from django.core.management.base import BaseCommand

from tunga_tasks.models import Task
from tunga_tasks.tasks import distribute_task_payment


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Distribute task payments.
        """
        # command to run: python manage.py tunga_distribute_task_payments

        tasks = Task.objects.filter(closed=True, pay_distributed=False)
        for task in tasks:
            distribute_task_payment(task.id)
