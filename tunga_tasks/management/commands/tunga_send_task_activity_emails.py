import datetime

from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db.models.aggregates import Sum
from django.db.models.expressions import Case, When, F
from django.db.models.fields import IntegerField
from django.db.models.query_utils import Q

from tunga.settings import TUNGA_URL
from tunga_activity import verbs
from tunga_activity.models import ActivityReadLog
from tunga_settings.slugs import TASK_ACTIVITY_UPDATE_EMAIL
from tunga_tasks.models import Participation, Task
from tunga_utils.emails import send_mail


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Send new task activity notifications
        """
        # command to run: python manage.py tunga_send_task_activity_emails

        # Initialize missing logs
        client_tasks = Task.objects.filter(closed=False).annotate(user_logs=Sum(
            Case(
                When(
                    read_logs__user=F('user'),
                    then=1
                ),
                default=0,
                output_field=IntegerField()
            )
        )).filter(user_logs=0)

        for task in client_tasks:
            ActivityReadLog.objects.update_or_create(
                user=task.user,
                content_type=ContentType.objects.get_for_model(task),
                object_id=task.id
            )

        participants = Participation.objects.filter(task__closed=False).annotate(user_logs=Sum(
            Case(
                When(
                    task__read_logs__user=F('user'),
                    then=1
                ),
                default=0,
                output_field=IntegerField()
            )
        )).filter(user_logs=0)

        for participant in participants:
            ActivityReadLog.objects.update_or_create(
                user=participant.user,
                content_type=ContentType.objects.get_for_model(participant.task),
                object_id=participant.task.id
            )

        # Send notifications
        utc_now = datetime.datetime.utcnow()
        min_date = utc_now - relativedelta(minutes=30)  # 30 minute window to read new messages
        min_last_email_date = utc_now - relativedelta(hours=3)  # Limit to 1 email every 3 hours per channel
        commission_date = parse('2016-08-28 00:00:00')  # Don't notify about events before the commissioning date
        user_tasks = ActivityReadLog.objects.filter(
            (
                Q(last_email_at__isnull=True) |
                Q(last_email_at__lt=min_last_email_date)
            ) &
            (
                Q(tasks__user=F('user')) | Q(tasks__participants=F('user'))
            )
        ).exclude(
            user__userswitchsetting__setting__slug=TASK_ACTIVITY_UPDATE_EMAIL,
            user__userswitchsetting__value=False
        ).annotate(new_activity=Sum(
            Case(
                When(
                    ~Q(tasks__activity_objects__actor_object_id=F('user_id')) &
                    Q(tasks__activity_objects__gt=F('last_read')) &
                    Q(tasks__activity_objects__timestamp__lte=min_date) &
                    Q(tasks__activity_objects__timestamp__gte=commission_date) &
                    (Q(last_email_at__isnull=True) | Q(tasks__activity_objects__timestamp__gt=F('last_email_at'))) &
                    Q(tasks__activity_objects__verb__in=[verbs.COMMENT, verbs.UPLOAD]),
                    then=1
                ),
                default=0,
                output_field=IntegerField()
            )
        )).filter(new_activity__gt=0)

        for user_task in user_tasks:
            task = user_task.content_object

            to = [user_task.user.email]
            subject = "New activity for task: {}".format(task.summary)
            ctx = {
                'receiver': user_task.user,
                'new_activity': user_task.new_activity,
                'task': user_task.content_object,
                'task_url': '%s/task/%s/' % (TUNGA_URL, user_task.object_id)
            }

            if send_mail(
                    subject, 'tunga/email/unread_task_activity', to, ctx, **dict(deal_ids=[task.hubspot_deal_id])
            ):
                user_task.last_email_at = datetime.datetime.utcnow()
                user_task.save()
