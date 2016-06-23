from django.contrib.auth import get_user_model
from django.db.models import When, Case, IntegerField
from django.db.models.aggregates import Sum
from django.db.models.expressions import F

from tunga.settings import EMAIL_SUBJECT_PREFIX, TUNGA_URL, TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS
from tunga_auth.filterbackends import my_connections_q_filter
from tunga_auth.models import USER_TYPE_DEVELOPER
from tunga_settings.models import VISIBILITY_DEVELOPER, VISIBILITY_MY_TEAM
from tunga_utils.decorators import catch_all_exceptions
from tunga_utils.emails import send_mail


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

        developers = None
        if queryset:
            developers = queryset[:15]

        subject = "%s New task created by %s" % (EMAIL_SUBJECT_PREFIX, instance.user.first_name)
        to = TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS
        bcc = [dev.email for dev in developers] if developers else None
        ctx = {
            'owner': instance.user,
            'task': instance,
            'task_url': '%s/task/%s/' % (TUNGA_URL, instance.id)
        }
        send_mail(subject, 'tunga/email/email_new_task.txt', to, ctx, bcc=bcc)


@catch_all_exceptions
def send_new_task_invitation_email(instance):
    subject = "%s Task invitation from %s" % (EMAIL_SUBJECT_PREFIX, instance.created_by.first_name)
    to = [instance.user.email]
    ctx = {
        'inviter': instance.created_by,
        'invitee': instance.user,
        'task': instance.task,
        'task_url': '%s/task/%s/' % (TUNGA_URL, instance.task.id)
    }
    send_mail(subject, 'tunga/email/email_new_task_invitation', to, ctx)


@catch_all_exceptions
def send_new_task_invitation_response_email(instance):
    subject = "%s Task invitation %s by %s" % (
        EMAIL_SUBJECT_PREFIX, instance.accepted and 'accepted' or 'rejected', instance.user.first_name)
    to = [instance.created_by.email]
    ctx = {
        'inviter': instance.created_by,
        'invitee': instance.user,
        'accepted': instance.accepted,
        'task': instance.task,
        'task_url': '%s/task/%s/' % (TUNGA_URL, instance.task.id)
    }
    send_mail(subject, 'tunga/email/email_task_invitation_response', to, ctx)


@catch_all_exceptions
def send_new_task_application_email(instance):
    subject = "%s New application from %s" % (EMAIL_SUBJECT_PREFIX, instance.user.first_name)
    to = [instance.task.user.email]
    ctx = {
        'owner': instance.task.user,
        'applicant': instance.user,
        'task': instance.task,
        'task_url': '%s/task/%s/' % (TUNGA_URL, instance.task.id)
    }
    send_mail(subject, 'tunga/email/email_new_task_application', to, ctx)


@catch_all_exceptions
def send_new_task_application_response_email(instance):
    subject = "%s Task application %s" % (EMAIL_SUBJECT_PREFIX, instance.accepted and 'accepted' or 'rejected')
    to = [instance.user.email]
    ctx = {
        'owner': instance.task.user,
        'applicant': instance.user,
        'accepted': instance.accepted,
        'task': instance.task,
        'task_url': '%s/task/%s/' % (TUNGA_URL, instance.task.id)
    }
    send_mail(subject, 'tunga/email/email_task_application_response', to, ctx)


@catch_all_exceptions
def send_new_task_application_applicant_email(instance):
    subject = "%s You applied for a task: %s" % (EMAIL_SUBJECT_PREFIX, instance.task.summary)
    to = [instance.user.email]
    ctx = {
        'owner': instance.task.user,
        'applicant': instance.user,
        'task': instance.task,
        'task_url': '%s/task/%s/' % (TUNGA_URL, instance.task.id)
    }
    send_mail(subject, 'tunga/email/email_new_task_application_applicant', to, ctx)


@catch_all_exceptions
def send_task_application_not_selected_email(instance):
    rejected_applicants = instance.application_set.filter(responded=False)
    if rejected_applicants:
        subject = "%s Your application was not accepted for: %s" % (EMAIL_SUBJECT_PREFIX, instance.summary)
        to = [rejected_applicants[0].user.email]
        bcc = [dev.user.email for dev in rejected_applicants[1:]] if len(rejected_applicants) > 1 else None
        ctx = {
            'task': instance,
            'task_url': '%s/task/%s/' % (TUNGA_URL, instance.id)
        }
        send_mail(subject, 'tunga/email/email_task_application_not_selected', to, ctx, bcc=bcc)
