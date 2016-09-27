import datetime

from django.contrib.auth import get_user_model
from django.db.models import When, Case, IntegerField
from django.db.models.aggregates import Sum
from django.db.models.expressions import F
from django.template.defaultfilters import truncatewords
from django_rq.decorators import job

from tunga.settings import EMAIL_SUBJECT_PREFIX, TUNGA_URL, TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS, SLACK_ATTACHMENT_COLOR_TUNGA, \
    TUNGA_ICON_URL_150, TUNGA_NAME, SLACK_ATTACHMENT_COLOR_RED, SLACK_ATTACHMENT_COLOR_GREEN
from tunga_auth.filterbackends import my_connections_q_filter
from tunga_tasks import slugs
from tunga_utils import slack_utils
from tunga_utils.constants import USER_TYPE_DEVELOPER, VISIBILITY_DEVELOPER, VISIBILITY_MY_TEAM
from tunga_settings import slugs as settings_slugs
from tunga_settings.utils import check_switch_setting
from tunga_tasks.models import Task, Participation, Application, ProgressEvent, ProgressReport
from tunga_utils.helpers import clean_instance, convert_to_text
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
def notify_task_invitation_response(instance):
    notify_task_invitation_response_email(instance)
    notify_task_invitation_response_slack(instance)


@job
def notify_task_invitation_response_email(instance):
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
def notify_task_invitation_response_slack(instance):
    instance = clean_instance(instance, Participation)

    if not slack_utils.is_task_notification_enabled(instance.task, slugs.EVENT_APPLY):
        return

    webhook_url = slack_utils.get_webhook_url(instance.task.user)
    if webhook_url:
        task_url = '%s/task/%s/' % (TUNGA_URL, instance.task_id)
        summary = "Task invitation %s by %s %s" % (
            instance.accepted and 'accepted' or 'rejected', instance.user.short_name,
            instance.accepted and ':smiley: :fireworks: :+1:' or ':unamused:'
        )
        task_description = ''
        if instance.task.description:
            task_description = '%s\n\n<%s|View details on Tunga>' % \
                          (truncatewords(convert_to_text(instance.task.description), 20), task_url)
        slack_msg = {
            slack_utils.KEY_ATTACHMENTS: [
                {
                    slack_utils.KEY_PRETEXT: summary,
                    slack_utils.KEY_TITLE: instance.task.summary,
                    slack_utils.KEY_TITLE_LINK: task_url,
                    slack_utils.KEY_TEXT: task_description,
                    slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT, slack_utils.KEY_FOOTER],
                    slack_utils.KEY_COLOR: instance.accepted and SLACK_ATTACHMENT_COLOR_GREEN or SLACK_ATTACHMENT_COLOR_RED,
                    slack_utils.KEY_FOOTER: TUNGA_NAME,
                    slack_utils.KEY_FOOTER_ICON: TUNGA_ICON_URL_150,
                    slack_utils.KEY_FALLBACK: summary
                }
            ]
        }
        slack_utils.send_incoming_webhook(webhook_url, slack_msg)


@job
def notify_new_task_application(instance):
    notify_new_task_application_email(instance)
    notify_new_task_application_slack(instance)


@job
def notify_new_task_application_email(instance):
    instance = clean_instance(instance, Application)
    if not check_switch_setting(instance.task.user, settings_slugs.NEW_TASK_APPLICATION_EMAIL):
        return
    subject = "%s New application from %s" % (EMAIL_SUBJECT_PREFIX, instance.user.short_name)
    to = [instance.task.user.email]
    ctx = {
        'owner': instance.task.user,
        'applicant': instance.user,
        'task': instance.task,
        'task_url': '%s/task/%s/applications/' % (TUNGA_URL, instance.task_id)
    }
    send_mail(subject, 'tunga/email/email_new_task_application', to, ctx)


@job
def notify_new_task_application_slack(instance):
    instance = clean_instance(instance, Application)

    if not slack_utils.is_task_notification_enabled(instance.task, slugs.EVENT_APPLY):
        return

    webhook_url = slack_utils.get_webhook_url(instance.task.user)
    if webhook_url:
        application_url = '%s/task/%s/applications/' % (TUNGA_URL, instance.task_id)
        summary = "New application from %s" % instance.user.short_name
        slack_msg = {
            slack_utils.KEY_ATTACHMENTS: [
                {
                    slack_utils.KEY_PRETEXT: summary,
                    slack_utils.KEY_AUTHOR_NAME: instance.user.display_name,
                    slack_utils.KEY_TITLE: instance.task.summary,
                    slack_utils.KEY_TITLE_LINK: application_url,
                    slack_utils.KEY_TEXT: '%s\n\n<%s|View details on Tunga>' %
                                          (truncatewords(convert_to_text(instance.pitch), 20), application_url),
                    slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT, slack_utils.KEY_FOOTER],
                    slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_TUNGA,
                    slack_utils.KEY_FOOTER: TUNGA_NAME,
                    slack_utils.KEY_FOOTER_ICON: TUNGA_ICON_URL_150,
                    slack_utils.KEY_FALLBACK: summary
                }
            ]
        }
        slack_utils.send_incoming_webhook(webhook_url, slack_msg)


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
def notify_new_progress_report(instance):
    notify_new_progress_report_email(instance)
    notify_new_progress_report_slack(instance)

@job
def notify_new_progress_report_email(instance):
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
def notify_new_progress_report_slack(instance):
    instance = clean_instance(instance, ProgressReport)

    if not slack_utils.is_task_notification_enabled(instance.event.task, slugs.EVENT_PROGRESS):
        return

    webhook_url = slack_utils.get_webhook_url(instance.event.task.user)
    if webhook_url:
        report_url = '%s/task/%s/event/%s/' % (TUNGA_URL, instance.event.task_id, instance.event_id)
        summary = "%s submitted a Progress Report" % instance.user.display_name
        slack_msg = {
            slack_utils.KEY_ATTACHMENTS: [
                {
                    slack_utils.KEY_PRETEXT: summary,
                    slack_utils.KEY_AUTHOR_NAME: instance.user.display_name,
                    slack_utils.KEY_TITLE: instance.event.task.summary,
                    slack_utils.KEY_TITLE_LINK: report_url,
                    slack_utils.KEY_TEXT: 'Status: %s'
                                          '\nPercentage completed: %s%s'
                                          '\n\n<%s|View details on Tunga>' %
                                          (instance.get_status_display(), instance.percentage, '%', report_url),
                    slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT, slack_utils.KEY_FOOTER],
                    slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_TUNGA,
                    slack_utils.KEY_FOOTER: TUNGA_NAME,
                    slack_utils.KEY_FOOTER_ICON: TUNGA_ICON_URL_150,
                    slack_utils.KEY_FALLBACK: summary
                }
            ]
        }
        slack_utils.send_incoming_webhook(webhook_url, slack_msg)


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
