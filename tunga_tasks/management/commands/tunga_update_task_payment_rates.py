from decimal import Decimal

from django.core.management.base import BaseCommand

from tunga_tasks.models import Task


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Fix payment rates based on task status
        """
        # command to run: python manage.py tunga_update_task_payment_rates

        # Initialize missing logs
        tasks = Task.objects.filter(closed=False)
        for task in tasks:
            active_participants = task.participation_set.filter(accepted=True).count()
            print(task.id, active_participants)
            if not active_participants:
                task.dev_rate = Decimal(19)
                task.pm_rate = Decimal(39)
                task.pm_time_percentage = Decimal(15)
                task.tunga_percentage_dev = Decimal('34.21')
                task.tunga_percentage_pm = Decimal('48.71')
                task.save()
