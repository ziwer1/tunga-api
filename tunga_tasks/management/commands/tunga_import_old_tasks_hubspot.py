import datetime
from tunga_tasks.models import Task
from tunga_tasks.utils import create_hubspot_deal
from django.core.management.base import BaseCommand

class Command(BaseCommand):

    def handle(self, *args, **options):
        tasks = Task.objects.exclude(hubspot_deal_id__isnull=False)
        epoch = datetime.datetime.utcfromtimestamp(0)

        for task in tasks:
            created_at = (task.created_at - epoch).total_seconds() * 1000.0
            create_hubspot_deal(task, createdate=created_at)
