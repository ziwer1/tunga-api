from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage
from django.db.models import When, Case, IntegerField
from django.db.models.aggregates import Sum
from django.db.models.expressions import F
from django.template.loader import render_to_string

from tunga.settings import EMAIL_SUBJECT_PREFIX
from tunga_auth.filterbackends import my_connections_q_filter
from tunga_auth.models import USER_TYPE_DEVELOPER
from tunga_settings.models import VISIBILITY_DEVELOPER, VISIBILITY_MY_TEAM
from tunga_utils.decorators import catch_all_exceptions


@catch_all_exceptions
def send_new_task_email(instance):
    if instance.visibility in [VISIBILITY_DEVELOPER, VISIBILITY_MY_TEAM]:
        queryset = get_user_model().objects.filter(type=USER_TYPE_DEVELOPER)
        if instance.visibility == VISIBILITY_MY_TEAM:
            queryset = queryset.filter(
                my_connections_q_filter(instance.user)
            )
        ordering = []
        task_skills = instance.skills.all()
        if task_skills:
            when = []
            for skill in task_skills:
                new_when = When(
                        userprofile__skills=skill,
                        then=1
                    )
                when.append(new_when)
            queryset = queryset.annotate(matches=Sum(
                Case(
                    *when,
                    default=0,
                    output_field=IntegerField()
                )
            ))
            ordering.append('-matches')
        ordering.append('-tasks_completed')
        queryset = queryset.annotate(
            tasks_completed=Sum(
                Case(
                    When(
                        participation__task__closed=True,
                        participation__user__id=F('id'),
                        participation__accepted=True,
                        then=1
                    ),
                    default=0,
                    output_field=IntegerField()
                )
            )
        )
        queryset = queryset.order_by(*ordering)
        print queryset.query
        print queryset.values()

        if queryset:
            developers = queryset[:20]

            subject = "%s New task created by %s" % (EMAIL_SUBJECT_PREFIX, instance.user.first_name)
            to = [developers[0]]
            bcc = developers[1:] if len(developers) > 1 else None

            message = render_to_string(
                'tunga/email/email_new_task.txt',
                {
                    'owner': instance.user,
                    'task': instance,
                    'task_url': 'http://tunga.io/task/%s/' % instance.id
                }
            )
            EmailMessage(subject, message, to=to, bcc=bcc).send()
