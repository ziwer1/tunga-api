import datetime

from django.contrib.auth import get_user_model
from django.db.models import When, Case, IntegerField
from django.db.models.aggregates import Sum
from django.db.models.expressions import F
from django_rq.decorators import job

from tunga.settings import EMAIL_SUBJECT_PREFIX, TUNGA_URL, TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS
from tunga_auth.filterbackends import my_connections_q_filter
from tunga_auth.models import USER_TYPE_DEVELOPER
from tunga_settings import slugs as settings_slugs
from tunga_settings.models import VISIBILITY_DEVELOPER, VISIBILITY_MY_TEAM
from tunga_settings.utils import check_switch_setting
from tunga_tasks.models import Task, Participation, Application, ProgressEvent, ProgressReport
from tunga_utils.decorators import clean_instance
from tunga_utils.emails import send_mail


@job
def send_new_task_email(instance):
    instance = clean_instance(instance, Task)

    developers = None
    if instance.visibility in [VISIBILITY_DEVELOPER, VISIBILITY_MY_TEAM]:
        queryset = get_user_model().objects.filter(
            type=USER_TYPE_DEVELOPER
        ).exclude(
            userswitchsetting__setting__slug=settings_slugs.NEW_TASK_EMAIL,
            userswitchsetting__value=False
        )
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
    send_mail(subject, 'tunga/email/email_new_task', to, ctx, bcc=bcc)


@job
def send_new_task_invitation_email(instance):
    instance = clean_instance(instance, Participation)
    if not check_switch_setting(instance.user, settings_slugs.NEW_TASK_INVITATION_EMAIL):
        return
    subject = "%s Task invitation from %s" % (EMAIL_SUBJECT_PREFIX, instance.task.user.first_name)
    to = [instance.user.email]
    ctx = {
        'inviter': instance.task.user,
        'invitee': instance.user,
        'task': instance.task,
        'task_url': '%s/task/%s/' % (TUNGA_URL, instance.task.id)
    }
    send_mail(subject, 'tunga/email/email_new_task_invitation', to, ctx)


@job
def send_new_task_invitation_response_email(instance):
    instance = clean_instance(instance, Participation)
    if not check_switch_setting(instance.task.user, settings_slugs.TASK_INVITATION_RESPONSE_EMAIL):
        return
    subject = "%s Task invitation %s by %s" % (
        EMAIL_SUBJECT_PREFIX, instance.accepted and 'accepted' or 'rejected', instance.user.first_name)
    to = [instance.task.user.email]
    ctx = {
        'inviter': instance.task.user,
        'invitee': instance.user,
        'accepted': instance.accepted,
        'task': instance.task,
        'task_url': '%s/task/%s/' % (TUNGA_URL, instance.task.id)
    }
    send_mail(subject, 'tunga/email/email_task_invitation_response', to, ctx)


@job
def send_new_task_application_email(instance):
    instance = clean_instance(instance, Application)
    if not check_switch_setting(instance.task.user, settings_slugs.NEW_TASK_APPLICATION_EMAIL):
        return
    subject = "%s New application from %s" % (EMAIL_SUBJECT_PREFIX, instance.user.first_name)
    to = [instance.task.user.email]
    ctx = {
        'owner': instance.task.user,
        'applicant': instance.user,
        'task': instance.task,
        'task_url': '%s/task/%s/' % (TUNGA_URL, instance.task.id)
    }
    send_mail(subject, 'tunga/email/email_new_task_application', to, ctx)


@job
def send_new_task_application_response_email(instance):
    instance = clean_instance(instance, Application)
    if not check_switch_setting(instance.user, settings_slugs.TASK_APPLICATION_RESPONSE_EMAIL):
        return
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


@job
def send_new_task_application_applicant_email(instance):
    instance = clean_instance(instance, Application)
    if not check_switch_setting(instance.user, settings_slugs.TASK_ACTIVITY_UPDATE_EMAIL):
        return
    subject = "%s You applied for a task: %s" % (EMAIL_SUBJECT_PREFIX, instance.task.summary)
    to = [instance.user.email]
    ctx = {
        'owner': instance.task.user,
        'applicant': instance.user,
        'task': instance.task,
        'task_url': '%s/task/%s/' % (TUNGA_URL, instance.task.id)
    }
    send_mail(subject, 'tunga/email/email_new_task_application_applicant', to, ctx)


@job
def send_task_application_not_selected_email(instance):
    instance = clean_instance(instance, Task)
    rejected_applicants = instance.application_set.filter(
        responded=False
    ).exclude(
        user__userswitchsetting__setting__slug=settings_slugs.TASK_APPLICATION_RESPONSE_EMAIL,
        user__userswitchsetting__value=False
    )
    if rejected_applicants:
        subject = "%s Your application was not accepted for: %s" % (EMAIL_SUBJECT_PREFIX, instance.summary)
        to = [rejected_applicants[0].user.email]
        bcc = [dev.user.email for dev in rejected_applicants[1:]] if len(rejected_applicants) > 1 else None
        ctx = {
            'task': instance,
            'task_url': '%s/task/%s/' % (TUNGA_URL, instance.id)
        }
        send_mail(subject, 'tunga/email/email_task_application_not_selected', to, ctx, bcc=bcc)


@job
def send_progress_event_reminder_email(instance):
    instance = clean_instance(instance, ProgressEvent)
    subject = "%s Upcoming Task Update" % (EMAIL_SUBJECT_PREFIX,)
    participants = instance.task.participation_set.filter(
        accepted=True
    ).exclude(
        user__userswitchsetting__setting__slug=settings_slugs.TASK_PROGRESS_REPORT_REMINDER_EMAIL,
        user__userswitchsetting__value=False
    )
    if participants:
        to = [participants[0].user.email]
        bcc = [participant.user.email for participant in participants[1:]] if participants.count() > 1 else None
        ctx = {
            'owner': instance.task.user,
            'event': instance,
            'update_url': '%s/task/%s/event/%s/' % (TUNGA_URL, instance.task.id, instance.id)
        }
        if send_mail(subject, 'tunga/email/email_progress_event_reminder', to, ctx, bcc=bcc):
            instance.last_reminder_at = datetime.datetime.utcnow()
            instance.save()


@job
def send_new_progress_report_email(instance):
    instance = clean_instance(instance, ProgressReport)
    subject = "%s %s submitted a Progress Report" % (EMAIL_SUBJECT_PREFIX, instance.user.display_name)
    if not check_switch_setting(instance.event.task.user, settings_slugs.TASK_ACTIVITY_UPDATE_EMAIL):
        return
    to = [instance.event.task.user.email]
    ctx = {
        'owner': instance.event.task.user,
        'reporter': instance.user,
        'event': instance.event,
        'report': instance,
        'update_url': '%s/task/%s/event/%s/' % (TUNGA_URL, instance.event.task.id, instance.event.id)
    }
    send_mail(subject, 'tunga/email/email_new_progress_report', to, ctx)


@job
def send_task_invoice_request_email(instance):
    instance = clean_instance(instance, Task)
    subject = "%s %s requested for an invoice" % (EMAIL_SUBJECT_PREFIX, instance.user.display_name)
    to = TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS
    ctx = {
        'owner': instance.user,
        'task': instance,
        'task_url': '%s/task/%s/' % (TUNGA_URL, instance.id),
        'invoice_url': '%s/task/%s/download/invoice/?format=pdf' % (TUNGA_URL, instance.id)
    }
    send_mail(subject, 'tunga/email/email_task_invoice_request', to, ctx)
