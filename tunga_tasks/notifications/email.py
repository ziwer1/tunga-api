# -*- coding: utf-8 -*-
import base64
import datetime

from django_rq import job
from weasyprint import HTML

from tunga.settings import TUNGA_URL, TUNGA_STAFF_LOW_LEVEL_UPDATE_EMAIL_RECIPIENTS, \
    TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS, \
    MANDRILL_VAR_FIRST_NAME, SLACK_DEBUGGING_INCOMING_WEBHOOK
from tunga_tasks.background import process_invoices
from tunga_tasks.models import Task, Quote, Estimate, Participation, Application, ProgressEvent, ProgressReport, \
    TaskInvoice
from tunga_tasks.utils import get_suggested_community_receivers
from tunga_utils import mandrill_utils, slack_utils
from tunga_utils.constants import TASK_SCOPE_TASK, TASK_SOURCE_NEW_USER, USER_TYPE_DEVELOPER, VISIBILITY_MY_TEAM, \
    STATUS_ACCEPTED, VISIBILITY_DEVELOPER, USER_TYPE_PROJECT_MANAGER, STATUS_SUBMITTED, STATUS_APPROVED, \
    STATUS_DECLINED, STATUS_REJECTED, STATUS_INITIAL, PROGRESS_EVENT_TYPE_PM, PROGRESS_EVENT_TYPE_CLIENT, \
    TASK_PAYMENT_METHOD_BANK
from tunga_utils.emails import send_mail
from tunga_utils.helpers import clean_instance


@job
def notify_new_task_client_drip_one(instance, template='welcome'):
    instance = clean_instance(instance, Task)

    if instance.source != TASK_SOURCE_NEW_USER:
        # Only target wizard users
        return False

    to = [instance.user.email]
    if instance.owner:
        to.append(instance.owner.email)

    task_url = '{}/task/{}/'.format(TUNGA_URL, instance.id)
    task_edit_url = '{}/task/{}/edit/complete-task/'.format(TUNGA_URL, instance.id)
    task_call_url = '{}/task/{}/edit/call/'.format(TUNGA_URL, instance.id)
    browse_url = '{}/people/filter/developers'.format(TUNGA_URL)

    if not instance.user.is_confirmed:
        url_prefix = '{}/reset-password/confirm/{}/{}?new_user=true&next='.format(
            TUNGA_URL, instance.user.uid, instance.user.generate_reset_token()
        )
        task_url = '{}{}'.format(url_prefix, task_url)
        task_edit_url = '{}{}'.format(url_prefix, task_edit_url)
        task_call_url = '{}{}'.format(url_prefix, task_call_url)
        browse_url = '{}{}'.format(url_prefix, browse_url)

    merge_vars = [
        mandrill_utils.create_merge_var(MANDRILL_VAR_FIRST_NAME, instance.user.first_name),
        mandrill_utils.create_merge_var('task_url', task_edit_url),
        mandrill_utils.create_merge_var('call_url', task_call_url),
        mandrill_utils.create_merge_var('browse_url', browse_url)
    ]

    template_code = None
    if template == 'welcome':
        if instance.schedule_call_start:
            template_code = '01-b-welcome-call-scheduled'
            merge_vars.extend(
                [
                    mandrill_utils.create_merge_var('date', instance.schedule_call_start.strftime("%d %b, %Y")),
                    mandrill_utils.create_merge_var('time', instance.schedule_call_start.strftime("%I:%M%p")),
                ]
            )
        else:
            template_code = '01-welcome-new'
    elif template == 'hiring':
        template_code = '02-hiring'

    if template_code:
        mandrill_response = mandrill_utils.send_email(template_code, to, merge_vars=merge_vars)
        if mandrill_response:
            instance.last_drip_mail = template
            instance.last_drip_mail_at = datetime.datetime.utcnow()
            instance.save()

            mandrill_utils.log_emails.delay(mandrill_response, to, deal_ids=[instance.hubspot_deal_id])

            # Notify via Slack of sent email to double check and prevent multiple sends
            slack_utils.send_incoming_webhook(
                SLACK_DEBUGGING_INCOMING_WEBHOOK,
                {
                    slack_utils.KEY_TEXT: "Mandrill Email sent to {} for  <{}|{}>".format(', '.join(to), task_url, instance.summary),
                    slack_utils.KEY_CHANNEL: '#alerts'
                }
            )


@job
def notify_new_task_client_receipt_email(instance, reminder=False):
    instance = clean_instance(instance, Task)

    if instance.source == TASK_SOURCE_NEW_USER:
        return

    subject = "Your {} has been posted on Tunga".format(
        instance.scope == TASK_SCOPE_TASK and 'task' or 'project'
    )
    if instance.is_task and not instance.approved:
        subject = "{}Finalize your {}".format(
            reminder and 'Reminder: ' or '',
            instance.scope == TASK_SCOPE_TASK and 'task' or 'project'
        )
    to = [instance.user.email]
    if instance.owner:
        to.append(instance.owner.email)

    ctx = {
        'owner': instance.owner or instance.user,
        'task': instance,
        'task_url': '{}/task/{}/'.format(TUNGA_URL, instance.id),
        'task_edit_url': '{}/task/{}/edit/complete-task/'.format(TUNGA_URL, instance.id)
    }

    if instance.source == TASK_SOURCE_NEW_USER and not instance.user.is_confirmed:
        url_prefix = '{}/reset-password/confirm/{}/{}?new_user=true&next='.format(
            TUNGA_URL, instance.user.uid, instance.user.generate_reset_token()
        )
        ctx['task_url'] = '{}{}'.format(url_prefix, ctx['task_url'])
        ctx['task_edit_url'] = '{}{}'.format(url_prefix, ctx['task_edit_url'])

    if instance.is_task:
        if instance.approved:
            email_template = 'tunga/email/new_task_client_approved'
        else:
            if reminder:
                email_template = 'tunga/email/new_task_client_more_info_reminder'
            else:
                email_template = 'tunga/email/new_task_client_more_info'
    else:
        email_template = 'tunga/email/new_task_client_approved'
    if send_mail(subject, email_template, to, ctx, **dict(deal_ids=[instance.hubspot_deal_id])):
        if not instance.approved:
            instance.complete_task_email_at = datetime.datetime.utcnow()
            if reminder:
                instance.reminded_complete_task = True
            instance.save()


@job
def notify_new_task_admin_email(instance, new_user=False, completed=False, call_scheduled=False):
    instance = clean_instance(instance, Task)

    completed_phrase_subject = ''
    completed_phrase_body = ''
    if call_scheduled:
        completed_phrase_subject = 'availability window shared'
        completed_phrase_body = 'shared an availability window'
    elif completed:
        completed_phrase_subject = 'details completed'
        completed_phrase_body = 'completed the details'

    subject = "New{} {} {} by {}{}".format(
        (completed or call_scheduled) and ' wizard' or '',
        instance.scope == TASK_SCOPE_TASK and 'task' or 'project',
        completed_phrase_subject or 'created',
        instance.user.first_name, new_user and ' (New user)' or ''
    )

    to = TUNGA_STAFF_LOW_LEVEL_UPDATE_EMAIL_RECIPIENTS  # Notified via Slack so limit receiving admins

    ctx = {
        'owner': instance.owner or instance.user,
        'task': instance,
        'task_url': '{}/task/{}/'.format(TUNGA_URL, instance.id),
        'completed_phrase': completed_phrase_body,
    }
    send_mail(subject, 'tunga/email/new_task', to, ctx, **dict(deal_ids=[instance.hubspot_deal_id]))


@job
def notify_new_task_community_email(instance):
    instance = clean_instance(instance, Task)

    # Notify Devs or PMs
    community_receivers = None
    if instance.is_developer_ready:
        # Notify developers
        if instance.approved and instance.visibility in [VISIBILITY_DEVELOPER, VISIBILITY_MY_TEAM]:
            community_receivers = get_suggested_community_receivers(instance, user_type=USER_TYPE_DEVELOPER)
    elif instance.is_project and not instance.pm:
        community_receivers = get_suggested_community_receivers(instance, user_type=USER_TYPE_PROJECT_MANAGER)

    if instance.is_project and instance.pm:
        community_receivers = [instance.pm]

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
            'owner': instance.owner or instance.user,
            'task': instance,
            'task_url': '{}/work/{}/'.format(TUNGA_URL, instance.id)
        }
        send_mail(subject, 'tunga/email/new_task', to, ctx, bcc=bcc, **dict(deal_ids=[instance.hubspot_deal_id]))


VERB_MAP_STATUS_CHANGE = {
    STATUS_SUBMITTED: 'submitted',
    STATUS_APPROVED: 'approved',
    STATUS_DECLINED: 'declined',
    STATUS_ACCEPTED: 'accepted',
    STATUS_REJECTED: 'rejected'
}


@job
def notify_estimate_status_email(instance, estimate_type='estimate', target_admins=False):
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
            notify_estimate_status_email.delay(instance.id, estimate_type=estimate_type, target_admins=True)

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

    if send_mail(
            subject, 'tunga/email/estimate_status', to, ctx, **dict(deal_ids=[instance.task.hubspot_deal_id])
    ):
        if instance.status == STATUS_SUBMITTED:
            instance.moderator_email_at = datetime.datetime.utcnow()
            instance.save()
        if instance.status in [STATUS_ACCEPTED, STATUS_REJECTED]:
            instance.reviewed_email_at = datetime.datetime.utcnow()
            instance.save()

    if instance.status == STATUS_APPROVED:
        notify_estimate_approved_client_email(instance, estimate_type=estimate_type)


def notify_estimate_approved_client_email(instance, estimate_type='estimate'):
    instance = clean_instance(instance, estimate_type == 'quote' and Quote or Estimate)
    if instance.status != STATUS_APPROVED:
        return
    subject = "{} submitted {}".format(
        instance.user.first_name,
        estimate_type == 'estimate' and 'an estimate' or 'a quote'
    )
    to = [instance.task.user.email]
    if instance.task.owner:
        to.append(instance.task.owner.email)
    ctx = {
        'owner': instance.user,
        'estimate': instance,
        'task': instance.task,
        'estimate_url': '{}/work/{}/{}/{}'.format(TUNGA_URL, instance.task.id, estimate_type, instance.id),
        'actor': instance.user,
        'target': instance.task.owner or instance.task.user,
        'verb': 'submitted',
        'noun': estimate_type
    }

    if instance.task.source == TASK_SOURCE_NEW_USER and not instance.task.user.is_confirmed:
        url_prefix = '{}/reset-password/confirm/{}/{}?new_user=true&next='.format(
            TUNGA_URL, instance.user.uid, instance.user.generate_reset_token()
        )
        ctx['estimate_url'] = '{}{}'.format(url_prefix, ctx['estimate_url'])

    if send_mail(
            subject, 'tunga/email/estimate_status', to, ctx, **dict(deal_ids=[instance.task.hubspot_deal_id])
    ):
        instance.reviewer_email_at = datetime.datetime.utcnow()
        instance.save()


@job
def notify_task_invitation_email(instance):
    instance = clean_instance(instance, Participation)
    subject = "Task invitation from {}".format(instance.created_by.first_name)
    to = [instance.user.email]
    ctx = {
        'inviter': instance.created_by,
        'invitee': instance.user,
        'task': instance.task,
        'task_url': '{}/work/{}/'.format(TUNGA_URL, instance.task.id)
    }
    send_mail(
        subject, 'tunga/email/new_task_invitation', to, ctx, **dict(deal_ids=[instance.task.hubspot_deal_id])
    )


@job
def notify_task_invitation_project_owner_email(instance):
    instance = clean_instance(instance, Task)
    if not instance.owner:
        return
    subject = "{} invited you to a {}".format(instance.user.first_name, instance.is_task and 'task' or 'project')
    to = [instance.owner.email]
    ctx = {
        'inviter': instance.user,
        'invitee': instance.owner,
        'task': instance,
        'task_url': '{}/work/{}/'.format(TUNGA_URL, instance.id)
    }

    if not instance.owner.is_confirmed:
        url_prefix = '{}/reset-password/confirm/{}/{}?new_user=true&next='.format(
            TUNGA_URL, instance.owner.uid, instance.owner.generate_reset_token()
        )
        ctx['task_url'] = '{}{}'.format(url_prefix, ctx['task_url'])
    send_mail(
        subject, 'tunga/email/new_task_invitation_po', to, ctx, **dict(deal_ids=[instance.hubspot_deal_id])
    )


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
        'task_url': '{}/work/{}/'.format(TUNGA_URL, instance.task.id)
    }
    send_mail(
        subject, 'tunga/email/task_invitation_response', to, ctx, **dict(deal_ids=[instance.task.hubspot_deal_id])
    )


@job
def notify_new_task_application_owner_email(instance):
    instance = clean_instance(instance, Application)
    subject = "New application from {}".format(instance.user.short_name)
    to = [instance.task.user.email]
    if instance.task.owner:
        to.append(instance.task.owner.email)
    ctx = {
        'owner': instance.task.owner or instance.task.user,
        'applicant': instance.user,
        'task': instance.task,
        'task_url': '%s/work/%s/applications/' % (TUNGA_URL, instance.task_id)
    }

    if instance.task.source == TASK_SOURCE_NEW_USER and not instance.user.is_confirmed:
        url_prefix = '{}/reset-password/confirm/{}/{}?new_user=true&next='.format(
            TUNGA_URL, instance.user.uid, instance.user.generate_reset_token()
        )
        ctx['task_url'] = '{}{}'.format(url_prefix, ctx['task_url'])
    send_mail(
        subject, 'tunga/email/new_task_application', to, ctx, **dict(deal_ids=[instance.task.hubspot_deal_id])
    )


@job
def confirm_task_application_to_applicant_email(instance):
    instance = clean_instance(instance, Application)
    subject = "You applied for a task: {}".format(instance.task.summary)
    to = [instance.user.email]
    ctx = {
        'owner': instance.task.owner or instance.task.user,
        'applicant': instance.user,
        'task': instance.task,
        'task_url': '%s/work/%s/' % (TUNGA_URL, instance.task.id)
    }
    send_mail(
        subject, 'tunga/email/new_task_application_applicant', to, ctx,
        **dict(deal_ids=[instance.task.hubspot_deal_id])
    )


@job
def notify_task_application_response_owner_email(instance):
    instance = clean_instance(instance, Application)
    subject = "Task application {}".format(instance.status == STATUS_ACCEPTED and 'accepted' or 'rejected')
    to = [instance.user.email]
    ctx = {
        'owner': instance.task.owner or instance.task.user,
        'applicant': instance.user,
        'accepted': instance.status == STATUS_ACCEPTED,
        'task': instance.task,
        'task_url': '%s/work/%s/' % (TUNGA_URL, instance.task.id)
    }
    send_mail(
        subject, 'tunga/email/task_application_response', to, ctx,
        **dict(deal_ids=[instance.task.hubspot_deal_id])
    )


@job
def notify_task_application_response_admin_email(instance):
    instance = clean_instance(instance, Application)
    subject = "Task application {}".format(instance.status == STATUS_ACCEPTED and 'accepted' or 'rejected')
    to = TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS
    ctx = {
        'owner': instance.task.owner or instance.task.user,
        'applicant': instance.user,
        'accepted': instance.status == STATUS_ACCEPTED,
        'task': instance.task,
        'task_url': '%s/work/%s/' % (TUNGA_URL, instance.task.id)
    }
    send_mail(
        subject, 'tunga/email/task_application_response', to, ctx,
        **dict(deal_ids=[instance.task.hubspot_deal_id])
    )


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
        send_mail(
            subject, 'tunga/email/task_application_not_selected', to, ctx, bcc=bcc,
            **dict(deal_ids=[instance.hubspot_deal_id])
        )


@job
def remind_progress_event_email(instance):
    instance = clean_instance(instance, ProgressEvent)

    is_pm_report = instance.type == PROGRESS_EVENT_TYPE_PM
    is_client_report = instance.type == PROGRESS_EVENT_TYPE_CLIENT
    is_pm_or_client_report = is_pm_report or is_client_report

    if is_pm_report and not instance.task.is_project:
        return

    pm = instance.task.pm
    if not pm and instance.task.user.is_project_manager:
        pm = instance.task.user

    if is_pm_report and not pm:
        return

    owner = instance.task.owner
    if not owner:
        owner = instance.task.user

    if is_client_report and not owner:
        return

    subject = is_client_report and "Weekly Survey" or "Upcoming {} Update".format(
        instance.task.is_task and 'Task' or 'Project')

    to = []
    bcc = None
    if is_pm_report:
        to = [pm.email]
        bcc = None
    elif is_client_report:
        to = [owner.email]
        if owner.email != instance.task.user.email:
            to.append(instance.task.user.email)
        admins = instance.task.admins
        if admins:
            to.extend([user.email for user in admins])
        bcc = None
    else:
        participants = instance.task.participation_set.filter(status=STATUS_ACCEPTED, updates_enabled=True)
        if participants:
            to = [participants[0].user.email]
            bcc = [participant.user.email for participant in participants[1:]] if participants.count() > 1 else None
    ctx = {
        'owner': instance.task.owner or instance.task.user,
        'event': instance,
        'update_url': '%s/work/%s/event/%s/' % (TUNGA_URL, instance.task.id, instance.id)
    }

    if to:
        email_template = is_client_report and 'client_survey_reminder' or 'progress_event_reminder'
        if send_mail(
                subject, 'tunga/email/{}'.format(email_template), to, ctx, bcc=bcc,
                **dict(deal_ids=[instance.task.hubspot_deal_id])
        ):
            instance.last_reminder_at = datetime.datetime.utcnow()
            instance.save()


@job
def notify_new_progress_report_email(instance):
    instance = clean_instance(instance, ProgressReport)
    is_pm_report = instance.event.type == PROGRESS_EVENT_TYPE_PM
    is_client_report = instance.event.type == PROGRESS_EVENT_TYPE_CLIENT
    is_pm_or_client_report = is_pm_report or is_client_report
    is_dev_report = not is_pm_or_client_report

    subject = "{} submitted a {}".format(
        instance.user.display_name, is_client_report and "Weekly Survey" or "Progress Report"
    )

    to = is_pm_or_client_report and TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS or [instance.event.task.user.email]
    if is_dev_report:
        if instance.event.task.owner:
            to.append(instance.event.task.owner.email)
        admins = instance.event.task.admins
        if admins:
            to.extend([user.email for user in admins])
    ctx = {
        'owner': instance.event.task.owner or instance.event.task.user,
        'reporter': instance.user,
        'event': instance.event,
        'report': instance,
        'update_url': '{}/work/{}/event/{}/'.format(TUNGA_URL, instance.event.task.id, instance.event.id)
    }

    email_template = is_client_report and 'new_client_survey' or 'new_progress_report{}'.format(
        is_pm_report and '_pm' or ''
    )
    send_mail(
        subject, 'tunga/email/{}'.format(email_template), to, ctx,
        **dict(deal_ids=[instance.event.task.hubspot_deal_id])
    )


# Deadline missed
@job
def notify_progress_report_deadline_missed_email_admin(instance):
    instance = clean_instance(instance, ProgressReport)

    subject = "Following up on missed deadline"

    to = TUNGA_STAFF_LOW_LEVEL_UPDATE_EMAIL_RECIPIENTS

    ctx = {
        'owner': instance.event.task.owner or instance.event.task.user,
        'reporter': instance.user,
        'pm': instance.event.task.pm,
        'event': instance.event,
        'report': instance,
        'developers': instance.event.task.active_participants,
        'update_url': '{}/work/{}/event/{}/'.format(TUNGA_URL, instance.event.task.id, instance.event.id)
    }

    send_mail(
        subject, 'tunga/email/deadline_missed_admin', to, ctx,
        **dict(deal_ids=[instance.event.task.hubspot_deal_id])
    )


@job
def notify_progress_report_deadline_missed_email_client(instance):
    instance = clean_instance(instance, ProgressReport)

    subject = "Following up on missed deadline"

    to = [instance.event.task.user.email]
    if instance.event.task.owner:
        to.append(instance.event.task.owner.email)

    ctx = {
        'owner': instance.event.task.owner or instance.event.task.user,
        'reporter': instance.user,
        'event': instance.event,
        'report': instance,
        'update_url': '{}/work/{}/event/{}/'.format(TUNGA_URL, instance.event.task.id, instance.event.id)
    }

    send_mail(
        subject, 'tunga/email/deadline_missed_client', to, ctx,
        **dict(deal_ids=[instance.event.task.hubspot_deal_id])
    )


@job
def notify_progress_report_deadline_missed_email_pm(instance):
    instance = clean_instance(instance, ProgressReport)

    subject = "Following up on missed deadline"

    pm = instance.event.task.pm
    if not pm:
        return

    to = [pm.email]

    ctx = {
        'owner': instance.event.task.owner or instance.event.task.user,
        'reporter': instance.user,
        'pm': pm,
        'event': instance.event,
        'report': instance,
        'update_url': '{}/work/{}/event/{}/'.format(TUNGA_URL, instance.event.task.id, instance.event.id)
    }

    send_mail(
        subject, 'tunga/email/deadline_missed_pm', to, ctx,
        **dict(deal_ids=[instance.event.task.hubspot_deal_id])
    )


@job
def notify_progress_report_deadline_missed_email_dev(instance):
    instance = clean_instance(instance, ProgressReport)

    subject = "Following up on missed deadline"

    to = [instance.user.email]

    ctx = {
        'owner': instance.event.task.owner or instance.event.task.user,
        'reporter': instance.user,
        'event': instance.event,
        'report': instance,
        'update_url': '{}/work/{}/event/{}/'.format(TUNGA_URL, instance.event.task.id, instance.event.id)
    }

    send_mail(
        subject, 'tunga/email/deadline_missed_dev', to, ctx,
        **dict(deal_ids=[instance.event.task.hubspot_deal_id])
    )


# More than 20% difference in time spent and accomplished
@job
def notify_progress_report_behind_schedule_by_algo_email_admin(instance):
    instance = clean_instance(instance, ProgressReport)

    subject = "Alert (!): {} is running behind schedule".format(
        instance.event.task.is_task and 'Task' or 'Project'
    )

    to = TUNGA_STAFF_LOW_LEVEL_UPDATE_EMAIL_RECIPIENTS

    ctx = {
        'owner': instance.event.task.owner or instance.event.task.user,
        'reporter': instance.user,
        'pm': instance.event.task.pm,
        'event': instance.event,
        'report': instance,
        'developers': instance.event.task.active_participants,
        'update_url': '{}/work/{}/event/{}/'.format(TUNGA_URL, instance.event.task.id, instance.event.id)
    }

    send_mail(
        subject, 'tunga/email/behind_schedule_by_algo_admin', to, ctx,
        **dict(deal_ids=[instance.event.task.hubspot_deal_id])
    )


@job
def notify_progress_report_behind_schedule_by_algo_email_pm(instance):
    instance = clean_instance(instance, ProgressReport)

    subject = "Alert (!): it appears you're behind schedule"

    pm = instance.event.task.pm
    if not pm:
        return

    to = [pm.email]

    ctx = {
        'owner': instance.event.task.owner or instance.event.task.user,
        'reporter': instance.user,
        'pm': pm,
        'event': instance.event,
        'report': instance,
        'update_url': '{}/work/{}/event/{}/'.format(TUNGA_URL, instance.event.task.id, instance.event.id)
    }

    send_mail(
        subject, 'tunga/email/behind_schedule_by_algo_pm', to, ctx,
        **dict(deal_ids=[instance.event.task.hubspot_deal_id])
    )


@job
def notify_progress_report_behind_schedule_by_algo_email_dev(instance):
    instance = clean_instance(instance, ProgressReport)

    subject = "Alert (!): it appears you're behind schedule"

    to = [instance.user.email]

    ctx = {
        'owner': instance.event.task.owner or instance.event.task.user,
        'reporter': instance.user,
        'event': instance.event,
        'report': instance,
        'update_url': '{}/work/{}/event/{}/'.format(TUNGA_URL, instance.event.task.id, instance.event.id)
    }

    send_mail(
        subject, 'tunga/email/behind_schedule_by_algo_dev', to, ctx,
        **dict(deal_ids=[instance.event.task.hubspot_deal_id])
    )


# Client not satisfied with deliverable
@job
def notify_progress_report_client_not_satisfied_email_admin(instance):
    instance = clean_instance(instance, ProgressReport)

    subject = "Alert (!): Client dissatisfied"

    to = TUNGA_STAFF_LOW_LEVEL_UPDATE_EMAIL_RECIPIENTS

    ctx = {
        'owner': instance.event.task.owner or instance.event.task.user,
        'reporter': instance.user,
        'pm': instance.event.task.pm,
        'event': instance.event,
        'report': instance,
        'developers': instance.event.task.active_participants,
        'update_url': '{}/work/{}/event/{}/'.format(TUNGA_URL, instance.event.task.id, instance.event.id)
    }

    send_mail(
        subject, 'tunga/email/client_not_satisfied_admin', to, ctx,
        **dict(deal_ids=[instance.event.task.hubspot_deal_id])
    )


@job
def notify_progress_report_client_not_satisfied_email_client(instance):
    instance = clean_instance(instance, ProgressReport)

    subject = "Following up on {} quality".format(instance.event.task.is_task and 'task' or 'project')

    to = [instance.event.task.user.email]
    if instance.event.task.owner:
        to.append(instance.event.task.owner.email)

    ctx = {
        'owner': instance.event.task.owner or instance.event.task.user,
        'reporter': instance.user,
        'event': instance.event,
        'report': instance,
        'update_url': '{}/work/{}/event/{}/'.format(TUNGA_URL, instance.event.task.id, instance.event.id)
    }

    send_mail(
        subject, 'tunga/email/client_not_satisfied_client', to, ctx,
        **dict(deal_ids=[instance.event.task.hubspot_deal_id])
    )


@job
def notify_progress_report_client_not_satisfied_email_pm(instance):
    instance = clean_instance(instance, ProgressReport)

    subject = "Alert (!): Client dissatisfied"

    pm = instance.event.task.pm
    if not pm:
        return

    to = [pm.email]

    ctx = {
        'owner': instance.event.task.owner or instance.event.task.user,
        'reporter': instance.user,
        'pm': pm,
        'event': instance.event,
        'report': instance,
        'update_url': '{}/work/{}/event/{}/'.format(TUNGA_URL, instance.event.task.id, instance.event.id)
    }

    send_mail(
        subject, 'tunga/email/client_not_satisfied_pm', to, ctx,
        **dict(deal_ids=[instance.event.task.hubspot_deal_id])
    )


@job
def notify_progress_report_client_not_satisfied_email_dev(instance):
    instance = clean_instance(instance, ProgressReport)

    subject = "Alert (!): Client dissatisfied"

    to = [instance.user.email]

    ctx = {
        'owner': instance.event.task.owner or instance.event.task.user,
        'reporter': instance.user,
        'event': instance.event,
        'report': instance,
        'update_url': '{}/work/{}/event/{}/'.format(TUNGA_URL, instance.event.task.id, instance.event.id)
    }

    send_mail(
        subject, 'tunga/email/client_not_satisfied_dev', to, ctx,
        **dict(deal_ids=[instance.event.task.hubspot_deal_id])
    )


# Stuck and/ or not progressing
@job
def notify_progress_report_stuck_email_admin(instance):
    instance = clean_instance(instance, ProgressReport)

    subject = "{} has been classified as stuck ".format(instance.event.task.is_task and 'Task' or 'Project')

    to = TUNGA_STAFF_LOW_LEVEL_UPDATE_EMAIL_RECIPIENTS

    ctx = {
        'owner': instance.event.task.owner or instance.event.task.user,
        'reporter': instance.user,
        'pm': instance.event.task.pm,
        'event': instance.event,
        'report': instance,
        'developers': instance.event.task.active_participants,
        'update_url': '{}/work/{}/event/{}/'.format(TUNGA_URL, instance.event.task.id, instance.event.id)
    }

    send_mail(
        subject, 'tunga/email/report_stuck_admin', to, ctx,
        **dict(deal_ids=[instance.event.task.hubspot_deal_id])
    )


@job
def notify_progress_report_stuck_email_pm(instance):
    instance = clean_instance(instance, ProgressReport)

    subject = "You guys are stuck, but help is underway."

    pm = instance.event.task.pm
    if not pm:
        return

    to = [pm.email]

    ctx = {
        'owner': instance.event.task.owner or instance.event.task.user,
        'reporter': instance.user,
        'pm': pm,
        'event': instance.event,
        'report': instance,
        'update_url': '{}/work/{}/event/{}/'.format(TUNGA_URL, instance.event.task.id, instance.event.id)
    }

    send_mail(
        subject, 'tunga/email/report_stuck_pm', to, ctx,
        **dict(deal_ids=[instance.event.task.hubspot_deal_id])
    )


@job
def notify_progress_report_stuck_email_dev(instance):
    instance = clean_instance(instance, ProgressReport)

    subject = "You're stuck, but help is underway."

    to = [instance.user.email]

    ctx = {
        'owner': instance.event.task.owner or instance.event.task.user,
        'reporter': instance.user,
        'event': instance.event,
        'report': instance,
        'update_url': '{}/work/{}/event/{}/'.format(TUNGA_URL, instance.event.task.id, instance.event.id)
    }

    send_mail(
        subject, 'tunga/email/report_stuck_dev', to, ctx,
        **dict(deal_ids=[instance.event.task.hubspot_deal_id])
    )


# Won't meet deadline
@job
def notify_progress_report_wont_meet_deadline_email_admin(instance):
    instance = clean_instance(instance, ProgressReport)

    subject = "`Alert (!):` {} doesn't expect to meet the deadline".format(
        instance.event.type == PROGRESS_EVENT_TYPE_PM and 'PM' or 'Developer'
    )

    to = TUNGA_STAFF_LOW_LEVEL_UPDATE_EMAIL_RECIPIENTS

    ctx = {
        'owner': instance.event.task.owner or instance.event.task.user,
        'reporter': instance.user,
        'pm': instance.event.task.pm,
        'event': instance.event,
        'report': instance,
        'developers': instance.event.task.active_participants,
        'update_url': '{}/work/{}/event/{}/'.format(TUNGA_URL, instance.event.task.id, instance.event.id)
    }

    send_mail(
        subject, 'tunga/email/wont_meet_deadline_admin', to, ctx,
        **dict(deal_ids=[instance.event.task.hubspot_deal_id])
    )


@job
def notify_progress_report_wont_meet_deadline_email_pm(instance):
    instance = clean_instance(instance, ProgressReport)

    subject = "`Alert (!):` {} doesn't expect to meet the deadline".format(
        instance.event.type == PROGRESS_EVENT_TYPE_PM and 'PM' or 'Developer'
    )

    pm = instance.event.task.pm
    if not pm:
        return

    to = [pm.email]

    ctx = {
        'owner': instance.event.task.owner or instance.event.task.user,
        'reporter': instance.user,
        'pm': pm,
        'event': instance.event,
        'report': instance,
        'update_url': '{}/work/{}/event/{}/'.format(TUNGA_URL, instance.event.task.id, instance.event.id)
    }

    send_mail(
        subject, 'tunga/email/wont_meet_deadline_pm', to, ctx,
        **dict(deal_ids=[instance.event.task.hubspot_deal_id])
    )


@job
def notify_progress_report_wont_meet_deadline_email_dev(instance):
    instance = clean_instance(instance, ProgressReport)

    subject = "`Alert (!):` {} doesn't expect to meet the deadline".format(
        instance.event.type == PROGRESS_EVENT_TYPE_PM and 'PM' or 'Developer'
    )

    to = [instance.user.email]

    ctx = {
        'owner': instance.event.task.owner or instance.event.task.user,
        'reporter': instance.user,
        'event': instance.event,
        'report': instance,
        'update_url': '{}/work/{}/event/{}/'.format(TUNGA_URL, instance.event.task.id, instance.event.id)
    }

    send_mail(
        subject, 'tunga/email/wont_meet_deadline_dev', to, ctx,
        **dict(deal_ids=[instance.event.task.hubspot_deal_id])
    )


@job
def notify_parties_of_low_rating_email(instance):
    instance = clean_instance(instance, ProgressReport)
    is_client_report = instance.event.type == PROGRESS_EVENT_TYPE_CLIENT

    if is_client_report:
        subject = "Work Rating For {}".format(instance.event.task.summary)
        ctx = {
            'owner': instance.event.task.owner or instance.event.task.user,
            'event': instance,
            'update_url': '{}/work/{}/event/{}/'.format(TUNGA_URL, instance.event.task.id, instance.event.id)
        }
        # send to client
        if instance.task.owner:
            to = [instance.event.task.owner.email]
            email_template = 'low_rating_client'
            send_mail(
                subject, 'tunga/email/{}'.format(email_template), to, ctx,
                **dict(deal_ids=[instance.event.task.hubspot_deal_id])
            )
        # send to pm
        if instance.event.task.pm:
            to = [instance.event.task.pm.email]
            email_template = 'low_rating_pm'
            send_mail(
                subject, 'tunga/email/{}'.format(email_template), to, ctx,
                **dict(deal_ids=[instance.event.task.hubspot_deal_id])
            )
        # send to user
        if instance.event.task.user:
            to = [instance.event.task.user.email]
            email_template = 'low_rating_user'
            send_mail(
                subject, 'tunga/email/{}'.format(email_template), to, ctx,
                **dict(deal_ids=[instance.event.task.hubspot_deal_id])
            )


@job
def notify_new_task_invoice_client_email(instance):
    instance = clean_instance(instance, TaskInvoice)

    to = [instance.user.email]
    if instance.task.owner and instance.task.owner.email != instance.user.email:
        to.append(instance.task.owner.email)

    if instance.task.user and instance.task.user.email != instance.user.email:
        to.append(instance.task.user.email)

    task_url = '{}/task/{}/'.format(TUNGA_URL, instance.task.id)

    owner = instance.task.owner or instance.task.user

    merge_vars = [
        mandrill_utils.create_merge_var(MANDRILL_VAR_FIRST_NAME, owner.first_name),
        mandrill_utils.create_merge_var('invoice_title', instance.task.summary),
        mandrill_utils.create_merge_var(
            'can_pay',
            bool(instance.payment_method != TASK_PAYMENT_METHOD_BANK and not instance.task.payment_approved)
        ),
    ]

    rendered_html = process_invoices(instance.task.id, invoice_types=('client',), user_id=owner.id, is_admin=False)
    pdf_file = HTML(string=rendered_html, encoding='utf-8').write_pdf()
    pdf_file_contents = base64.b64encode(pdf_file)

    attachments = [
        dict(
            content=pdf_file_contents,
            name='Invoice - {}'.format(instance.task.summary),
            type='application/pdf'
        )
    ]

    mandrill_response = mandrill_utils.send_email('69-invoice', to, merge_vars=merge_vars, attachments=attachments)
    if mandrill_response:
        mandrill_utils.log_emails.delay(mandrill_response, to, deal_ids=[instance.task.hubspot_deal_id])

        # Notify via Slack of sent email to double check and prevent multiple sends
        slack_utils.send_incoming_webhook(
            SLACK_DEBUGGING_INCOMING_WEBHOOK,
            {
                slack_utils.KEY_TEXT: "Mandrill Email sent to {} for <{}|Invoice: {}>".format(
                    ', '.join(to), task_url, instance.task.summary
                ),
                slack_utils.KEY_CHANNEL: '#alerts'
            }
        )


@job
def notify_new_task_invoice_admin_email(instance):
    instance = clean_instance(instance, TaskInvoice)
    subject = "{} generated for an invoice".format(instance.user.display_name)
    to = TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS
    ctx = {
        'user': instance.user,
        'owner': instance.task.owner or instance.task.user,
        'invoice': instance,
        'task': instance.task,
        'task_url': '{}/work/{}/'.format(TUNGA_URL, instance.task.id),
        'invoice_url': '{}/api/task/{}/download/invoice/?format=pdf'.format(TUNGA_URL, instance.task.id)
    }
    send_mail(
        subject, 'tunga/email/task_invoice_request', to, ctx, **dict(deal_ids=[instance.task.hubspot_deal_id])
    )


@job
def notify_payment_link_client_email(instance):
    instance = clean_instance(instance, Task)

    to = [instance.user.email]
    if instance.owner and instance.owner.email != instance.user.email:
        to.append(instance.owner.email)

    task_url = '{}/task/{}/'.format(TUNGA_URL, instance.id)
    payment_link = '{}pay/'.format(task_url)

    owner = instance.owner or instance.user

    merge_vars = [
        mandrill_utils.create_merge_var(MANDRILL_VAR_FIRST_NAME, owner.first_name),
        mandrill_utils.create_merge_var('payment_title', instance.summary),
        mandrill_utils.create_merge_var('payment_link', payment_link),
    ]

    mandrill_response = mandrill_utils.send_email('70-payment-link-ready', to, merge_vars=merge_vars)
    if mandrill_response:
        instance.payment_link_sent = True
        instance.payment_link_sent_at = datetime.datetime.utcnow()
        instance.save()

        mandrill_utils.log_emails.delay(mandrill_response, to, deal_ids=[instance.hubspot_deal_id])

        # Notify via Slack of sent email to double check and prevent multiple sends
        slack_utils.send_incoming_webhook(
            SLACK_DEBUGGING_INCOMING_WEBHOOK,
            {
                slack_utils.KEY_TEXT: "Mandrill Email sent to {} for <{}|Payment Link: {}>".format(
                    ', '.join(to), task_url, instance.summary
                ),
                slack_utils.KEY_CHANNEL: '#alerts'
            }
        )
