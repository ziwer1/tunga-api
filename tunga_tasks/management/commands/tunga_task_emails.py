from django.core.management.base import BaseCommand

from tunga_tasks.models import Task
from tunga_tasks.notifications import send_new_task_client_receipt_email, send_estimate_status_email
from tunga_tasks.tasks import distribute_task_payment


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Distribute task payments.
        """
        # command to run: python manage.py tunga_task_emails

        send_new_task_client_receipt_email(82)

        #send_estimate_status_email(7, estimate_type='quote')
