import datetime

from django_rq import job

from tunga.settings import TUNGA_URL, TUNGA_STAFF_LOW_LEVEL_UPDATE_EMAIL_RECIPIENTS, TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS
from tunga_tasks.models import Task, Quote, Estimate, Participation, Application, ProgressEvent, ProgressReport
from tunga_tasks.utils import get_suggested_community_receivers
from tunga_utils.constants import TASK_SCOPE_TASK, TASK_SOURCE_NEW_USER, USER_TYPE_DEVELOPER, VISIBILITY_MY_TEAM, \
    STATUS_ACCEPTED, VISIBILITY_DEVELOPER, USER_TYPE_PROJECT_MANAGER, STATUS_SUBMITTED, STATUS_APPROVED, \
    STATUS_DECLINED, STATUS_REJECTED, STATUS_INITIAL, PROGRESS_EVENT_TYPE_PM, PROGRESS_EVENT_TYPE_CLIENT, \
    PROGRESS_REPORT_STATUS_STUCK, PROGRESS_REPORT_STATUS_BEHIND_AND_STUCK
from tunga_utils.emails import send_mail
from tunga_utils.helpers import clean_instance


@job
def notify_new_task_client_receipt_email(instance, new_user=False, reminder=False):
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
    if instance.owner:
        to.append(instance.owner.email)

    ctx = {
        'owner': instance.owner or instance.user,
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
        'task_url': '%s/task/%s/' % (TUNGA_URL, instance.id),
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
        'task_url': '%s/work/%s/' % (TUNGA_URL, instance.task.id)
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
        'task_url': '%s/work/%s/' % (TUNGA_URL, instance.id)
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
        'task_url': '%s/work/%s/' % (TUNGA_URL, instance.task.id)
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

    subject = is_client_report and "Weekly Survey" or "Upcoming {} Update".format(instance.task.is_task and 'Task' or 'Project')

    to = []
    bcc = None
    if is_pm_report:
        to = [pm.email]
        bcc = None
    elif is_client_report:
        to = [owner.email]
        if owner.email != instance.task.user.email:
            to.append(instance.task.user.email)
        bcc = None
    else:
        participants = instance.task.participation_set.filter(status=STATUS_ACCEPTED)
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
    if instance.event.task.owner and not is_pm_or_client_report:
        to.append(instance.event.task.owner.email)
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


@job
def notify_task_invoice_request_email(instance):
    instance = clean_instance(instance, Task)
    subject = "{} requested for an invoice".format(instance.user.display_name)
    to = TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS
    ctx = {
        'owner': instance.owner or instance.user,
        'task': instance,
        'task_url': '%s/work/%s/' % (TUNGA_URL, instance.id),
        'invoice_url': '%s/api/task/%s/download/invoice/?format=pdf' % (TUNGA_URL, instance.id)
    }
    send_mail(
        subject, 'tunga/email/task_invoice_request', to, ctx, **dict(deal_ids=[instance.hubspot_deal_id])
    )


@job
def trigger_progress_report_actionable_events_emails(instance):
    instance = clean_instance(instance, ProgressReport)
    is_pm_report = instance.event.type == PROGRESS_EVENT_TYPE_PM
    is_client_report = instance.event.type == PROGRESS_EVENT_TYPE_CLIENT
    is_pm_or_client_report = is_pm_report or is_client_report
    is_dev_report = not is_pm_or_client_report

    if is_client_report and instance.rate_deliverables > 1 and instance.rate_deliverables < 4 and instance.deliverable_satisfaction:
        subject = "A deadline has been missed on the {} project".format(instance.event.task.summary)
        to = TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS

        ctx = {
            'owner': instance.event.task.owner or instance.event.task.user,
            'reporter': instance.user,
            'event': instance.event,
            'report': instance
        }

        email_template = 'deliverable_rating_below_standard'
        send_mail(
            subject, 'tunga/email/{}'.format(email_template), to, ctx,
            **dict(deal_ids=[instance.event.task.hubspot_deal_id])
        )

    if (is_pm_report or is_dev_report) and (instance.status == PROGRESS_REPORT_STATUS_STUCK or  instance.status == PROGRESS_REPORT_STATUS_BEHIND_AND_STUCK):

        subject = "Status has been reported Stuck on the {} project".format(instance.event.task.summary)
        to = TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS

        ctx = {
            'owner': instance.event.task.owner or instance.event.task.user,
            'reporter': instance.user,
            'event': instance.event,
            'report': instance,
        }

        email_template = 'project_status_stuck'
        send_mail(
            subject, 'tunga/email/{}'.format(email_template), to, ctx,
            **dict(deal_ids=[instance.event.task.hubspot_deal_id])
        )

    if instance.next_deadline_meet == False and (is_pm_report or is_dev_report):

        subject = "The Next Deadline will not be met on the {} project".format(instance.event.task.summary)
        to = TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS

        ctx = {
            'owner': instance.event.task.owner or instance.event.task.user,
            'reporter': instance.user,
            'event': instance.event,
            'report': instance
        }

        email_template = 'next_deadline_fail'
        send_mail(
            subject, 'tunga/email/{}'.format(email_template), to, ctx,
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
def notify_parties_of_low_rating_email(instance):
    instance = clean_instance(instance, ProgressReport)
    is_client_report = instance.event.type == PROGRESS_EVENT_TYPE_CLIENT

    if is_client_report:
        subject = "Work Rating For {}".format(instance.event.task.summary)
        ctx = {
            'owner': instance.event.task.owner or instance.event.task.user,
            'event': instance,
            'update_url': '%s/work/%s/event/%s/' % (TUNGA_URL, instance.event.task.id, instance.event.id)
        }
        # send to client
        if instance.task.owner:
            to = [instance.event.task.owner.email]
            email_template = 'notification_low_rating_client'
            send_mail(
                subject, 'tunga/email/{}'.format(email_template), to, ctx,
                **dict(deal_ids=[instance.event.task.hubspot_deal_id])
            )
        # send to pm
        if instance.event.task.pm:
            to = [instance.event.task.pm.email]
            email_template = 'notification_low_rating_pm'
            send_mail(
                subject, 'tunga/email/{}'.format(email_template), to, ctx,
                **dict(deal_ids=[instance.event.task.hubspot_deal_id])
            )
        # send to user
        if instance.event.task.user:
            to = [instance.event.task.user.email]
            email_template = 'notification_low_rating_user'
            send_mail(
                subject, 'tunga/email/{}'.format(email_template), to, ctx,
                **dict(deal_ids=[instance.event.task.hubspot_deal_id])
            )


@job
def notify_pm_dev_when_stuck_email(instance):
    instance = clean_instance(instance, ProgressReport)

    is_pm_report = instance.event.type == PROGRESS_EVENT_TYPE_PM
    is_client_report = instance.event.type == PROGRESS_EVENT_TYPE_CLIENT
    is_pm_or_client_report = is_pm_report or is_client_report
    is_dev_report = not is_pm_or_client_report

    subject = "{} Follow Up on {}".format(instance.task.user.short_name, instance.event.task.summary)
    ctx = {
        'owner': instance.event.task.owner or instance.event.task.user,
        'event': instance.event,
        'update_url': '%s/work/%s/event/%s/' % (TUNGA_URL, instance.task.id, instance.id)
    }

    if is_pm_report:
            to = [instance.event.task.pm.email]
            email_template = 'follow_up_when_stuck_pm'
    else:
        if is_dev_report:
            to = [instance.event.task.user.email]
            email_template = 'follow_up_when_stuck_dev'

    send_mail(
        subject, 'tunga/email/{}'.format(email_template), to, ctx,
        **dict(deal_ids=[instance.event.task.hubspot_deal_id])
    )


@job
def notify_dev_pm_on_failure_to_meet_deadline_email(instance):
    instance = clean_instance(instance, ProgressReport)

    is_pm_report = instance.event.type == PROGRESS_EVENT_TYPE_PM
    is_client_report = instance.event.type == PROGRESS_EVENT_TYPE_CLIENT
    is_pm_or_client_report = is_pm_report or is_client_report
    is_dev_report = not is_pm_or_client_report

    subject = "{} Follow Up on {}".format(instance.event.task.user.short_name, instance.event.task.summary)
    ctx = {
        'owner': instance.event.task.owner or instance.task.user,
        'event': instance.event,
        'update_url': '%s/work/%s/event/%s/' % (TUNGA_URL, instance.task.id, instance.id)
    }
    to = [instance.event.task.pm.email]

    email_template = None
    if is_pm_report:
        email_template = 'follow_up_when_wont_meet_deadline_pm'
    elif is_dev_report:
        to.append(instance.event.task.user.email)
        email_template = 'follow_up_when_wont_meet_deadline_dev'

    if email_template:
        send_mail(
            subject, 'tunga/email/{}'.format(email_template), to, ctx,
            **dict(deal_ids=[instance.event.task.hubspot_deal_id])
        )