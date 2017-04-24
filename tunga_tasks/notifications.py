import datetime

from django.contrib.auth import get_user_model
from django.db.models import When, Case, IntegerField
from django.db.models.aggregates import Sum
from django.db.models.expressions import F
from django.template.defaultfilters import truncatewords, floatformat
from django_rq.decorators import job

from tunga.settings import TUNGA_URL, TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS, SLACK_ATTACHMENT_COLOR_TUNGA, \
    SLACK_ATTACHMENT_COLOR_RED, SLACK_ATTACHMENT_COLOR_GREEN, SLACK_ATTACHMENT_COLOR_NEUTRAL, \
    SLACK_ATTACHMENT_COLOR_BLUE, SLACK_DEVELOPER_INCOMING_WEBHOOK, SLACK_STAFF_INCOMING_WEBHOOK, \
    SLACK_STAFF_UPDATES_CHANNEL, SLACK_DEVELOPER_UPDATES_CHANNEL, SLACK_PMS_UPDATES_CHANNEL
from tunga_auth.filterbackends import my_connections_q_filter
from tunga_tasks import slugs
from tunga_tasks.models import Task, Participation, Application, ProgressEvent, ProgressReport, Quote, Estimate
from tunga_utils import slack_utils
from tunga_utils.constants import USER_TYPE_DEVELOPER, VISIBILITY_DEVELOPER, VISIBILITY_MY_TEAM, TASK_SCOPE_TASK, \
    USER_TYPE_PROJECT_MANAGER, TASK_SOURCE_NEW_USER, STATUS_INITIAL, STATUS_SUBMITTED, STATUS_APPROVED, STATUS_DECLINED, \
    STATUS_ACCEPTED, STATUS_REJECTED, PROGRESS_EVENT_TYPE_PM
from tunga_utils.emails import send_mail
from tunga_utils.helpers import clean_instance, convert_to_text


def create_task_slack_msg(task, summary=None, channel='#general'):
    task_url = '{}/work/{}/'.format(TUNGA_URL, task.id)
    attachments = [
        {
            slack_utils.KEY_TITLE: task.summary,
            slack_utils.KEY_TITLE_LINK: task_url,
            slack_utils.KEY_TEXT: task.excerpt,
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_TUNGA
        }
    ]
    extra_details = ''
    if task.type:
        extra_details += '*Type*: {}\n'.format(task.get_type_display())
    if task.skills:
        extra_details += '*Skills*: {}\n'.format(task.skills_list)
    if task.deadline:
        extra_details += '*Deadline*: {}\n'.format(task.deadline.strftime('%d/%b/%Y'))
    if task.fee:
        amount = task.is_developer_ready and task.pay_dev or task.pay
        extra_details += '*Fee*: EUR {}\n'.format(floatformat(amount, arg=-2))
    if extra_details:
        attachments.append({
            slack_utils.KEY_TEXT: extra_details,
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_GREEN
        })
    if task.deliverables:
        attachments.append({
            slack_utils.KEY_TITLE: 'Deliverables',
            slack_utils.KEY_TEXT: task.deliverables,
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_BLUE
        })
    if task.stack_description:
        attachments.append({
            slack_utils.KEY_TITLE: 'Tech Stack',
            slack_utils.KEY_TEXT: task.stack_description,
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_NEUTRAL
        })
    if not summary:
        summary = "New {} created by {} | <{}|View on Tunga>".format(
            task.scope == TASK_SCOPE_TASK and 'task' or 'project',
            task.user.first_name, task_url)
    return {
        slack_utils.KEY_TEXT: summary,
        slack_utils.KEY_CHANNEL: channel,
        slack_utils.KEY_ATTACHMENTS: attachments
    }


@job
def notify_new_task(instance, new_user=False):
    send_new_task_client_receipt_email(instance)
    send_new_task_admin(instance, new_user=new_user)
    send_new_task_community(instance)


@job
def notify_task_approved(instance, new_user=False):
    send_new_task_client_receipt_email(instance)
    send_new_task_admin(instance, new_user=new_user, completed=True)
    send_new_task_community(instance)

@job
def send_new_task_client_receipt_email(instance, reminder=False):
    instance = clean_instance(instance, Task)
    subject = "Your {} has been posted on Tunga".format(
        instance.scope == TASK_SCOPE_TASK and 'task' or 'project'
    )
    if instance.is_task and not instance.approved:
        subject = "{}Finalize your {}".format(
            reminder and 'Reminder: ' or '',
            instance.scope == TASK_SCOPE_TASK and 'task' or 'project'
        )
    to = [instance.user.email]

    ctx = {
        'owner': instance.user,
        'task': instance,
        'task_url': '%s/task/%s/' % (TUNGA_URL, instance.id),
        'task_edit_url': '%s/task/%s/edit/complete-task/' % (TUNGA_URL, instance.id)
    }

    if instance.source == TASK_SOURCE_NEW_USER and not instance.user.is_confirmed:
        url_prefix = '{}/reset-password/confirm/{}/{}?new_user=true&next='.format(
            TUNGA_URL, instance.user.uid, instance.user.generate_reset_token()
        )
        ctx['task_url'] = '{}{}'.format(url_prefix, ctx['task_url'])
        ctx['task_edit_url'] = '{}{}'.format(url_prefix, ctx['task_edit_url'])

    if instance.is_task:
        if instance.approved:
            email_template = 'tunga/email/email_new_task_client_approved'
        else:
            if reminder:
                email_template = 'tunga/email/email_new_task_client_more_info_reminder'
            else:
                email_template = 'tunga/email/email_new_task_client_more_info'
    else:
        email_template = 'tunga/email/email_new_task_client_approved'
    if send_mail(subject, email_template, to, ctx):
        if not instance.approved:
            instance.complete_task_email_at = datetime.datetime.utcnow()
            if reminder:
                instance.reminded_complete_task = True
            instance.save()


@job
def send_new_task_admin(instance, new_user=False, completed=False):
    send_new_task_admin_email(instance, new_user=new_user, completed=completed)
    send_new_task_admin_slack(instance, new_user=new_user, completed=completed)

@job
def send_new_task_admin_email(instance, new_user=False, completed=False):
    instance = clean_instance(instance, Task)

    subject = "{} {} {} by {}{}".format(
        completed and 'New wizard' or 'New',
        instance.scope == TASK_SCOPE_TASK and 'task' or 'project',
        completed and 'details completed' or 'created',
        instance.user.first_name, new_user and ' (New user)' or ''
    )

    to = TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS
    ctx = {
        'owner': instance.user,
        'task': instance,
        'task_url': '%s/task/%s/' % (TUNGA_URL, instance.id),
        'completed': completed
    }
    send_mail(subject, 'tunga/email/email_new_task', to, ctx)


@job
def send_new_task_admin_slack(instance, new_user=False, completed=False):
    instance = clean_instance(instance, Task)
    task_url = '{}/work/{}/'.format(TUNGA_URL, instance.id)
    summary = "{} {} {} by {}{} | <{}|View on Tunga>".format(
        completed and 'New wizard' or 'New',
        instance.scope == TASK_SCOPE_TASK and 'task' or 'project',
        completed and 'details completed' or 'created',
        instance.user.first_name, new_user and ' (New user)' or '',
        task_url
    )
    slack_msg = create_task_slack_msg(instance, summary=summary, channel=SLACK_STAFF_UPDATES_CHANNEL)
    slack_utils.send_incoming_webhook(SLACK_STAFF_INCOMING_WEBHOOK, slack_msg)


@job
def send_reminder_task_applications(instance, admin=True):
    send_reminder_task_applications_slack(instance, admin=admin)


@job
def send_reminder_task_applications_slack(instance, admin=True):
    instance = clean_instance(instance, Task)

    if not instance.is_task:
        return
    task_url = '{}/work/{}/'.format(TUNGA_URL, instance.id)
    new_user = instance.source == TASK_SOURCE_NEW_USER

    summary = "Reminder: No applications yet for {} {} | <{}|View on Tunga>".format(
        instance.scope == TASK_SCOPE_TASK and 'task' or 'project',
        new_user and admin and ' (New user)' or '',
        task_url
    )
    slack_msg = create_task_slack_msg(
        instance, summary=summary,
        channel=admin and SLACK_STAFF_UPDATES_CHANNEL or SLACK_DEVELOPER_UPDATES_CHANNEL
    )
    slack_utils.send_incoming_webhook(
        admin and SLACK_STAFF_INCOMING_WEBHOOK or SLACK_DEVELOPER_INCOMING_WEBHOOK,
        slack_msg
    )


@job
def send_review_task_admin(instance):
    send_review_task_admin_slack(instance)


@job
def send_review_task_admin_slack(instance):
    instance = clean_instance(instance, Task)
    task_url = '{}/work/{}/'.format(TUNGA_URL, instance.id)
    new_user = instance.source == TASK_SOURCE_NEW_USER

    summary = "Reminder: Review {} {} | <{}|View on Tunga>\nCreated: {}".format(
        instance.scope == TASK_SCOPE_TASK and 'task' or 'project',
        new_user and ' (New user)' or '',
        task_url,
        instance.created_at.strftime("%d %b, %Y"),
        instance.approved_at and 'Approved: {}'.format(instance.approved_at.strftime("%d %b, %Y")) or '',
    )
    slack_msg = create_task_slack_msg(
        instance, summary=summary,
        channel=SLACK_STAFF_UPDATES_CHANNEL
    )
    slack_utils.send_incoming_webhook(
        SLACK_STAFF_INCOMING_WEBHOOK,
        slack_msg
    )


@job
def send_new_task_community(instance):
    send_new_task_community_email(instance)
    send_new_task_community_slack(instance)


@job
def send_new_task_community_email(instance):
    instance = clean_instance(instance, Task)

    # Notify Devs or PMs
    community_receivers = None
    if (not instance.is_developer_ready) or (instance.approved and instance.visibility in [VISIBILITY_DEVELOPER, VISIBILITY_MY_TEAM]):

        # Filter users based on nature of work
        queryset = get_user_model().objects.filter(
            type=instance.is_developer_ready and USER_TYPE_DEVELOPER or USER_TYPE_PROJECT_MANAGER
        )

        # Only developers on client's team
        if instance.is_developer_ready and instance.visibility == VISIBILITY_MY_TEAM:
            queryset = queryset.filter(
                my_connections_q_filter(instance.user)
            )

        ordering = []

        # Order by matching skills
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

        # Order developers by tasks completed
        if instance.is_developer_ready:
            queryset = queryset.annotate(
                tasks_completed=Sum(
                    Case(
                        When(
                            participation__task__closed=True,
                            participation__user__id=F('id'),
                            participation__status=STATUS_ACCEPTED,
                            then=1
                        ),
                        default=0,
                        output_field=IntegerField()
                    )
                )
            )
            ordering.append('-tasks_completed')

        if ordering:
            queryset = queryset.order_by(*ordering)
        if queryset:
            community_receivers = queryset[:15]

    subject = "New {} created by {}".format(
        instance.scope == TASK_SCOPE_TASK and 'task' or 'project',
        instance.user.first_name
    )

    if community_receivers:
        to = [community_receivers[0].email]
        bcc = None
        if len(community_receivers) > 1:
            bcc = [user.email for user in community_receivers[1:]] if community_receivers[1:] else None
        ctx = {
            'owner': instance.user,
            'task': instance,
            'task_url': '{}/work/{}/'.format(TUNGA_URL, instance.id)
        }
        send_mail(subject, 'tunga/email/email_new_task', to, ctx, bcc=bcc)


@job
def send_new_task_community_slack(instance):
    instance = clean_instance(instance, Task)

    # Notify Devs or PMs via Slack
    if (not instance.is_developer_ready) or (instance.approved and instance.visibility == VISIBILITY_DEVELOPER):
        slack_msg = create_task_slack_msg(
            instance,
            channel=instance.is_developer_ready and SLACK_DEVELOPER_UPDATES_CHANNEL or SLACK_PMS_UPDATES_CHANNEL
        )
        slack_utils.send_incoming_webhook(SLACK_DEVELOPER_INCOMING_WEBHOOK, slack_msg)


VERB_MAP_STATUS_CHANGE = {
    STATUS_SUBMITTED: 'submitted',
    STATUS_APPROVED: 'approved',
    STATUS_DECLINED: 'declined',
    STATUS_ACCEPTED: 'accepted',
    STATUS_REJECTED: 'rejected'
}


@job
def send_estimate_status_email(instance, estimate_type='estimate', target_admins=False):
    instance = clean_instance(instance, estimate_type == 'quote' and Quote or Estimate)
    if instance.status == STATUS_INITIAL:
        return

    actor = None
    target = None
    action_verb = VERB_MAP_STATUS_CHANGE.get(instance.status, None)
    recipients = None

    if instance.status in [STATUS_SUBMITTED]:
        actor = instance.user
        recipients = TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS
    elif instance.status in [STATUS_APPROVED, STATUS_DECLINED]:
        actor = instance.moderated_by
        target = instance.user
        recipients = [instance.user.email]
    elif instance.status in [STATUS_ACCEPTED, STATUS_REJECTED]:
        actor = instance.reviewed_by
        if target_admins:
            recipients = TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS
        else:
            target = instance.user
            recipients = [instance.user.email]

            # Notify staff in a separate email
            send_estimate_status_email.delay(instance.id, estimate_type=estimate_type, target_admins=True)

    subject = "{} {} {}".format(
        actor.first_name,
        action_verb,
        estimate_type == 'estimate' and 'an estimate' or 'a quote'
    )
    to = recipients

    ctx = {
        'owner': instance.user,
        'estimate': instance,
        'task': instance.task,
        'estimate_url': '{}/work/{}/{}/{}'.format(TUNGA_URL, instance.task.id, estimate_type, instance.id),
        'actor': actor,
        'target': target,
        'verb': action_verb,
        'noun': estimate_type
    }

    if send_mail(subject, 'tunga/email/email_estimate_status', to, ctx):
        if instance.status == STATUS_SUBMITTED:
            instance.moderator_email_at = datetime.datetime.utcnow()
            instance.save()
        if instance.status in [STATUS_ACCEPTED, STATUS_REJECTED]:
            instance.reviewed_email_at = datetime.datetime.utcnow()
            instance.save()

    if instance.status == STATUS_APPROVED:
        send_estimate_approved_client_email(instance, estimate_type=estimate_type)


def send_estimate_approved_client_email(instance, estimate_type='estimate'):
    instance = clean_instance(instance, estimate_type == 'quote' and Quote or Estimate)
    if instance.status != STATUS_APPROVED:
        return
    subject = "{} submitted {}".format(
        instance.user.first_name,
        estimate_type == 'estimate' and 'an estimate' or 'a quote'
    )
    to = [instance.task.user.email]
    ctx = {
        'owner': instance.user,
        'estimate': instance,
        'task': instance.task,
        'estimate_url': '{}/work/{}/{}/{}'.format(TUNGA_URL, instance.task.id, estimate_type, instance.id),
        'actor': instance.user,
        'target': instance.task.user,
        'verb': 'submitted',
        'noun': estimate_type
    }

    if instance.task.source == TASK_SOURCE_NEW_USER and not instance.task.user.is_confirmed:
        url_prefix = '{}/reset-password/confirm/{}/{}?new_user=true&next='.format(
            TUNGA_URL, instance.user.uid, instance.user.generate_reset_token()
        )
        ctx['estimate_url'] = '{}{}'.format(url_prefix, ctx['estimate_url'])

    if send_mail(subject, 'tunga/email/email_estimate_status', to, ctx):
        instance.reviewer_email_at = datetime.datetime.utcnow()
        instance.save()


@job
def send_new_task_invitation_email(instance):
    instance = clean_instance(instance, Participation)
    subject = "Task invitation from {}".format(instance.created_by.first_name)
    to = [instance.user.email]
    ctx = {
        'inviter': instance.created_by,
        'invitee': instance.user,
        'task': instance.task,
        'task_url': '%s/work/%s/' % (TUNGA_URL, instance.task.id)
    }
    send_mail(subject, 'tunga/email/email_new_task_invitation', to, ctx)


@job
def notify_task_invitation_response(instance):
    notify_task_invitation_response_email(instance)
    notify_task_invitation_response_slack(instance)


@job
def notify_task_invitation_response_email(instance):
    instance = clean_instance(instance, Participation)
    if instance.status not in [STATUS_ACCEPTED, STATUS_REJECTED]:
        return

    subject = "Task invitation {} by {}".format(
        instance.status == STATUS_ACCEPTED and 'accepted' or 'rejected', instance.user.first_name
    )
    to = list({instance.task.user.email, instance.created_by.email})
    ctx = {
        'inviter': instance.created_by,
        'invitee': instance.user,
        'accepted': instance.status == STATUS_ACCEPTED,
        'task': instance.task,
        'task_url': '%s/work/%s/' % (TUNGA_URL, instance.task.id)
    }
    send_mail(subject, 'tunga/email/email_task_invitation_response', to, ctx)


@job
def notify_task_invitation_response_slack(instance):
    instance = clean_instance(instance, Participation)

    if not slack_utils.is_task_notification_enabled(instance.task, slugs.EVENT_APPLICATION):
        return

    task_url = '%s/work/%s/' % (TUNGA_URL, instance.task_id)
    slack_msg = "Task invitation %s by %s %s\n\n<%s|View details on Tunga>" % (
        instance.status == STATUS_ACCEPTED and 'accepted' or 'rejected', instance.user.short_name,
        instance.status == STATUS_ACCEPTED and ':smiley: :fireworks:' or ':unamused:',
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
    subject = "New application from {}".format(instance.user.short_name)
    to = [instance.task.user.email]
    ctx = {
        'owner': instance.task.user,
        'applicant': instance.user,
        'task': instance.task,
        'task_url': '%s/work/%s/applications/' % (TUNGA_URL, instance.task_id)
    }

    if instance.task.source == TASK_SOURCE_NEW_USER and not instance.user.is_confirmed:
        url_prefix = '{}/reset-password/confirm/{}/{}?new_user=true&next='.format(
            TUNGA_URL, instance.user.uid, instance.user.generate_reset_token()
        )
        ctx['task_url'] = '{}{}'.format(url_prefix, ctx['task_url'])
    send_mail(subject, 'tunga/email/email_new_task_application', to, ctx)


@job
def notify_new_task_application_slack(instance):
    instance = clean_instance(instance, Application)

    if not slack_utils.is_task_notification_enabled(instance.task, slugs.EVENT_APPLICATION):
        return

    application_url = '%s/work/%s/applications/' % (TUNGA_URL, instance.task_id)
    slack_msg = "New application from %s" % instance.user.short_name
    attachments = [
        {
            slack_utils.KEY_TITLE: instance.task.summary,
            slack_utils.KEY_TITLE_LINK: application_url,
            slack_utils.KEY_TEXT: '%s%s%s%s\n\n<%s|View details on Tunga>' %
                                  (truncatewords(convert_to_text(instance.pitch), 100),
                                   instance.hours_needed and '\n*Workload:* {} hrs'.format(instance.hours_needed) or '',
                                   instance.deliver_at and '\n*Delivery Date:* {}'.format(
                                       instance.deliver_at.strftime("%d %b, %Y")
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
    subject = "Task application {}".format(instance.status == STATUS_ACCEPTED and 'accepted' or 'rejected')
    to = [instance.user.email]
    ctx = {
        'owner': instance.task.user,
        'applicant': instance.user,
        'accepted': instance.status == STATUS_ACCEPTED,
        'task': instance.task,
        'task_url': '%s/work/%s/' % (TUNGA_URL, instance.task.id)
    }
    send_mail(subject, 'tunga/email/email_task_application_response', to, ctx)


@job
def send_new_task_application_applicant_email(instance):
    instance = clean_instance(instance, Application)
    subject = "You applied for a task: {}".format(instance.task.summary)
    to = [instance.user.email]
    ctx = {
        'owner': instance.task.user,
        'applicant': instance.user,
        'task': instance.task,
        'task_url': '%s/work/%s/' % (TUNGA_URL, instance.task.id)
    }
    send_mail(subject, 'tunga/email/email_new_task_application_applicant', to, ctx)


@job
def send_task_application_not_selected_email(instance):
    instance = clean_instance(instance, Task)
    rejected_applicants = instance.application_set.filter(
        status=STATUS_REJECTED
    )
    if rejected_applicants:
        subject = "Your application was not accepted for: {}".format(instance.summary)
        to = [rejected_applicants[0].user.email]
        bcc = [dev.user.email for dev in rejected_applicants[1:]] if len(rejected_applicants) > 1 else None
        ctx = {
            'task': instance,
            'task_url': '%s/work/%s/' % (TUNGA_URL, instance.id)
        }
        send_mail(subject, 'tunga/email/email_task_application_not_selected', to, ctx, bcc=bcc)


@job
def send_progress_event_reminder(instance):
    send_progress_event_reminder_email(instance)


@job
def send_progress_event_reminder_email(instance):
    instance = clean_instance(instance, ProgressEvent)

    is_internal = instance.type == PROGRESS_EVENT_TYPE_PM
    if is_internal and not instance.task.is_project:
        return
    pm = instance.task.pm
    if not pm and instance.task.user.is_project_manager:
        pm = instance.task.user

    if is_internal and not pm:
        return

    subject = "Upcoming {} Update".format(instance.task.is_task and 'Task' or 'Project')
    participants = instance.task.participation_set.filter(status=STATUS_ACCEPTED)
    if participants:
        if is_internal:
            to = [pm.email]
            bcc = None
        else:
            to = [participants[0].user.email]
            bcc = [participant.user.email for participant in participants[1:]] if participants.count() > 1 else None
        ctx = {
            'owner': instance.task.user,
            'event': instance,
            'update_url': '%s/work/%s/event/%s/' % (TUNGA_URL, instance.task.id, instance.id)
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
    subject = "{} submitted a Progress Report".format(instance.user.display_name)

    is_internal = instance.event.type == PROGRESS_EVENT_TYPE_PM
    to = is_internal and TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS or [instance.event.task.user.email]
    ctx = {
        'owner': instance.event.task.user,
        'reporter': instance.user,
        'event': instance.event,
        'report': instance,
        'update_url': '%s/work/%s/event/%s/' % (TUNGA_URL, instance.event.task.id, instance.event.id)
    }
    send_mail(subject, 'tunga/email/email_new_progress_report{}'.format(is_internal and '_pm' or ''), to, ctx)

@job
def notify_new_progress_report_slack(instance):
    instance = clean_instance(instance, ProgressReport)

    is_internal = instance.event.type == PROGRESS_EVENT_TYPE_PM
    if not (slack_utils.is_task_notification_enabled(instance.event.task, slugs.EVENT_PROGRESS) or is_internal):
        return

    report_url = '%s/work/%s/event/%s/' % (TUNGA_URL, instance.event.task_id, instance.event_id)
    slack_msg = "%s submitted a Progress Report | %s" % (
        instance.user.display_name, '<{}|View details on Tunga>'.format(report_url)
    )

    slack_text_suffix = ''
    if is_internal:
        if instance.last_deadline_met is not None:
            slack_text_suffix = '\nWas the last deadline met?: {}'.format(instance.last_deadline_met and 'Yes' or 'No')
        if instance.next_deadline is not None:
            slack_text_suffix += '\nNext deadline: {}'.format(instance.next_deadline.strftime("%d %b, %Y"))
    attachments = [
        {
            slack_utils.KEY_TITLE: instance.event.task.summary,
            slack_utils.KEY_TITLE_LINK: report_url,
            slack_utils.KEY_TEXT: '*Status:* {}'
                                  '\n*Percentage completed:* {}{}{}'.format(
                instance.get_status_display(), instance.percentage, '%', slack_text_suffix
            ),
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_BLUE
        }
    ]

    if is_internal and instance.deadline_report:
        attachments.append({
            slack_utils.KEY_TITLE: 'Report about the last deadline:',
            slack_utils.KEY_TEXT: convert_to_text(instance.deadline_report),
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_RED
        })

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
    if is_internal and instance.team_appraisal:
        attachments.append({
            slack_utils.KEY_TITLE: 'Team appraisal:',
            slack_utils.KEY_TEXT: convert_to_text(instance.team_appraisal),
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_NEUTRAL
        })
    if instance.remarks:
        attachments.append({
            slack_utils.KEY_TITLE: 'Other remarks or questions',
            slack_utils.KEY_TEXT: convert_to_text(instance.remarks),
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_NEUTRAL
        })
    if is_internal:
        slack_utils.send_incoming_webhook(SLACK_STAFF_INCOMING_WEBHOOK, {
            slack_utils.KEY_TEXT: slack_msg,
            slack_utils.KEY_ATTACHMENTS: attachments
        })
    else:
        slack_utils.send_integration_message(instance.event.task, message=slack_msg, attachments=attachments)


@job
def send_task_invoice_request_email(instance):
    instance = clean_instance(instance, Task)
    subject = "{} requested for an invoice".format(instance.user.display_name)
    to = TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS
    ctx = {
        'owner': instance.user,
        'task': instance,
        'task_url': '%s/work/%s/' % (TUNGA_URL, instance.id),
        'invoice_url': '%s/api/task/%s/download/invoice/?format=pdf' % (TUNGA_URL, instance.id)
    }
    send_mail(subject, 'tunga/email/email_task_invoice_request', to, ctx)

@job
def send_new_task_app_admin_notif_slack(instance):
    instance = clean_instance(instance, Application)
    application_url = '{}/work/{}/'.format(TUNGA_URL, instance.id)
    summary = "New task application recieved from {} | <{}|View on Tunga>".format(
        'Developer', 
        application_url
    )
    slack_msg = create_task_slack_msg(instance, summary=summary, channel=SLACK_STAFF_UPDATES_CHANNEL)
    slack_utils.send_incoming_webhook(SLACK_STAFF_INCOMING_WEBHOOK, slack_msg)


@job
def send_new_task_app_admin_notif_email(instance):
    instance = clean_instance(instance, Application)
    subject = "Developer sent in an application"
    to = TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS
    ctx = {
        'owner': instance.user,
        'application': instance,
        'application_url': '%s/work/%s/' % (TUNGA_URL, instance.id)
    }
    send_mail(subject, 'tunga/email/email_task_application', to, ctx)


@job
def send_new_task_application_response_admin_email(instance):
    instance = clean_instance(instance, Application)
    subject = "Task application {}".format(instance.status == STATUS_ACCEPTED and 'accepted' or 'rejected')
    to = TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS
    ctx = {
        'owner': instance.task.user,
        'applicant': instance.user,
        'accepted': instance.status == STATUS_ACCEPTED,
        'task': instance.task,
        'task_url': '%s/work/%s/' % (TUNGA_URL, instance.task.id)
    }
    send_mail(subject, 'tunga/email/email_task_application_response', to, ctx)
