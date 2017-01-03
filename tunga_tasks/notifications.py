import datetime

from django.contrib.auth import get_user_model
from django.db.models import When, Case, IntegerField
from django.db.models.aggregates import Sum
from django.db.models.expressions import F
from django.template.defaultfilters import truncatewords
from django_rq.decorators import job

from tunga.settings import EMAIL_SUBJECT_PREFIX, TUNGA_URL, TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS, SLACK_ATTACHMENT_COLOR_TUNGA, \
    SLACK_ATTACHMENT_COLOR_RED, SLACK_ATTACHMENT_COLOR_GREEN, SLACK_ATTACHMENT_COLOR_NEUTRAL, \
    SLACK_ATTACHMENT_COLOR_BLUE
from tunga_auth.filterbackends import my_connections_q_filter
from tunga_tasks import slugs
from tunga_tasks.models import Task, Participation, Application, ProgressEvent, ProgressReport
from tunga_utils import slack_utils
from tunga_utils.constants import USER_TYPE_DEVELOPER, VISIBILITY_DEVELOPER, VISIBILITY_MY_TEAM
from tunga_utils.emails import send_mail
from tunga_utils.helpers import clean_instance, convert_to_text


@job
def send_new_task_email(instance):
    instance = clean_instance(instance, Task)

    developers = None
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

    if not slack_utils.is_task_notification_enabled(instance.task, slugs.EVENT_APPLICATION):
        return

    task_url = '%s/task/%s/' % (TUNGA_URL, instance.task_id)
    slack_msg = "Task invitation %s by %s %s\n\n<%s|View details on Tunga>" % (
        instance.accepted and 'accepted' or 'rejected', instance.user.short_name,
        instance.accepted and ':smiley: :fireworks:' or ':unamused:',
        task_url
    )
    slack_utils.send_integration_message(instance.task, message=slack_msg)


@job
def notify_new_task_application(instance):
    notify_new_task_application_email(instance)
    notify_new_task_application_slack(instance)


@job
def notify_new_task_application_email(instance):
    instance = clean_instance(instance, Application)
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

    if not slack_utils.is_task_notification_enabled(instance.task, slugs.EVENT_APPLICATION):
        return

    application_url = '%s/task/%s/applications/' % (TUNGA_URL, instance.task_id)
    slack_msg = "New application from %s" % instance.user.short_name
    attachments = [
        {
            slack_utils.KEY_TITLE: instance.task.summary,
            slack_utils.KEY_TITLE_LINK: application_url,
            slack_utils.KEY_TEXT: '%s%s%s%s\n\n<%s|View details on Tunga>' %
                                  (truncatewords(convert_to_text(instance.pitch), 100),
                                   instance.hours_needed and '\n*Workload:* {} hrs'.format(instance.hours_needed) or '',
                                   instance.deliver_at and '\n*Delivery Date:* {}'.format(
                                       instance.deliver_at.strftime("%d %b, %Y at %H:%M GMT")
                                   ) or '',
                                   instance.remarks and '\n*Remarks:* {}'.format(
                                       truncatewords(convert_to_text(instance.remarks), 100)
                                   ) or '',
                                   application_url),
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_TUNGA
        }
    ]
    slack_utils.send_integration_message(instance.task, message=slack_msg, attachments=attachments)


@job
def send_new_task_application_response_email(instance):
    instance = clean_instance(instance, Application)
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
    participants = instance.task.participation_set.filter(accepted=True)
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

    report_url = '%s/task/%s/event/%s/' % (TUNGA_URL, instance.event.task_id, instance.event_id)
    slack_msg = "%s submitted a Progress Report | %s" % (
        instance.user.display_name, '<{}|View details on Tunga>'.format(report_url)
    )
    attachments = [
        {
            slack_utils.KEY_TITLE: instance.event.task.summary,
            slack_utils.KEY_TITLE_LINK: report_url,
            slack_utils.KEY_TEXT: '*Status:* %s'
                                  '\n*Percentage completed:* %s%s' %
                                  (instance.get_status_display(), instance.percentage, '%'),
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_BLUE
        }
    ]
    if instance.accomplished:
        attachments.append({
            slack_utils.KEY_TITLE: 'What has been accomplished since last update?',
            slack_utils.KEY_TEXT: convert_to_text(instance.accomplished),
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_GREEN
        })
    if instance.next_steps:
        attachments.append({
            slack_utils.KEY_TITLE: 'What are the next next steps?',
            slack_utils.KEY_TEXT: convert_to_text(instance.next_steps),
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_BLUE
        })
    if instance.obstacles:
        attachments.append({
            slack_utils.KEY_TITLE: 'What obstacles are impeding your progress?',
            slack_utils.KEY_TEXT: convert_to_text(instance.obstacles),
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_RED
        })
    if instance.remarks:
        attachments.append({
            slack_utils.KEY_TITLE: 'Other remarks or questions',
            slack_utils.KEY_TEXT: convert_to_text(instance.remarks),
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_NEUTRAL
        })
    slack_utils.send_integration_message(instance.event.task, message=slack_msg, attachments=attachments)


@job
def send_task_invoice_request_email(instance):
    instance = clean_instance(instance, Task)
    subject = "%s %s requested for an invoice" % (EMAIL_SUBJECT_PREFIX, instance.user.display_name)
    to = TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS
    ctx = {
        'owner': instance.user,
        'task': instance,
        'task_url': '%s/task/%s/' % (TUNGA_URL, instance.id),
        'invoice_url': '%s/api/task/%s/download/invoice/?format=pdf' % (TUNGA_URL, instance.id)
    }
    send_mail(subject, 'tunga/email/email_task_invoice_request', to, ctx)
