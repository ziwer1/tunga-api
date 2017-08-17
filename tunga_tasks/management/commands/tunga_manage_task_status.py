import datetime

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand
from django.db.models.expressions import Case, When
from django.db.models.fields import DateTimeField

from tunga_tasks.models import Task
from tunga_tasks.notifications.generic import remind_no_task_applications, notify_review_task_admin
from tunga_utils.constants import TASK_SCOPE_TASK


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Update periodic update events and send notifications for upcoming update events.
        """
        # command to run: python manage.py tunga_manage_task_status

        # Choose tasks that aren't closed or under review already
        tasks_filter = Task.objects.filter(
            scope=TASK_SCOPE_TASK, closed=False, review=False
        ).annotate(
            activated_at=Case(
                When(
                    approved_at__isnull=True,
                    then='created_at'
                ),
                default='approved_at',
                output_field=DateTimeField()
            )
        )

        utc_now = datetime.datetime.utcnow()

        # Remind admins and devs about approved tasks with no applications 2 days after creation or approval
        min_date_no_applications = utc_now - relativedelta(days=2)
        min_date_no_developer_selected = utc_now - relativedelta(days=10)
        tasks_no_applications = tasks_filter.filter(
            approved=True, participants__isnull=False, activated_at__range=[
                min_date_no_developer_selected, min_date_no_applications
            ]
        )
        for task in tasks_no_applications:
            # Remind admins
            remind_no_task_applications.delay(task.id, admin=True)

            # Remind devs
            remind_no_task_applications.delay(task.id, admin=False)

        # Remind admins to take action on tasks with no accepted applications 10 days after creation or approval
        tasks_no_developers_selected = tasks_filter.filter(
            participants__isnull=True, created_at__lte=min_date_no_developer_selected
        )
        for task in tasks_no_developers_selected:
            # Put task in review
            task.review = True
            task.save()

            # Notify admins to take action
            notify_review_task_admin.delay(task.id)
