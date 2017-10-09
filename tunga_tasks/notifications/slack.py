# -*- coding: utf-8 -*-

import datetime

from django.template.defaultfilters import floatformat, truncatewords
from django_rq import job

from tunga.settings import TUNGA_URL, SLACK_ATTACHMENT_COLOR_TUNGA, SLACK_ATTACHMENT_COLOR_GREEN, \
    SLACK_ATTACHMENT_COLOR_BLUE, SLACK_ATTACHMENT_COLOR_NEUTRAL, SLACK_ATTACHMENT_COLOR_RED, \
    SLACK_STAFF_UPDATES_CHANNEL, SLACK_STAFF_INCOMING_WEBHOOK, SLACK_DEVELOPER_UPDATES_CHANNEL, \
    SLACK_DEVELOPER_INCOMING_WEBHOOK, SLACK_PMS_UPDATES_CHANNEL, SLACK_STAFF_LEADS_CHANNEL, \
    SLACK_STAFF_PROJECT_EXECUTION_CHANNEL, SLACK_STAFF_PAYMENTS_CHANNEL
from tunga_tasks import slugs
from tunga_tasks.models import Task, Participation, Application, ProgressEvent, ProgressReport, TaskInvoice
from tunga_tasks.utils import get_task_integration
from tunga_utils import slack_utils
from tunga_utils.constants import TASK_SCOPE_TASK, TASK_SOURCE_NEW_USER, VISIBILITY_DEVELOPER, STATUS_ACCEPTED, \
    APP_INTEGRATION_PROVIDER_SLACK, PROGRESS_EVENT_TYPE_PM, PROGRESS_EVENT_TYPE_CLIENT, TASK_PAYMENT_METHOD_BANK
from tunga_utils.helpers import clean_instance, convert_to_text
from tunga_utils.slack_utils import get_user_im_id


def create_task_slack_msg(task, summary='', channel='#general', show_schedule=True, show_contacts=False, is_admin=False):
    task_url = '{}/work/{}/'.format(TUNGA_URL, task.id)

    attachments = [
        {
            slack_utils.KEY_TITLE: task.summary,
            slack_utils.KEY_TITLE_LINK: task_url,
            slack_utils.KEY_TEXT: task.excerpt or task.summary,
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
        extra_details += '*Deadline*: {}\n'.format(task.deadline.strftime("%d %b, %Y"))
    if task.fee:
        amount = task.is_developer_ready and task.pay_dev or task.pay
        extra_details += '*Fee*: EUR {}\n'.format(floatformat(amount, arg=-2))
    if show_schedule and task.schedule_call_start:
        extra_details += '*Available*: \nDate: {}\nTime: {} {} UTC\n'.format(
            task.schedule_call_start.strftime("%d %b, %Y"),
            task.schedule_call_start.strftime("%I:%M%p"),
            task.schedule_call_end and ' - {}'.format(task.schedule_call_end.strftime("%I:%M%p")) or ''
        )
    if show_contacts:
        extra_details += '*Email*: {}\n'.format(task.user.email)
        if task.skype_id:
            extra_details += '*Skype ID or Call URL*: {}\n'.format(task.skype_id)
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
    if is_admin:
        developers = task.active_participants
        if developers:
            attachments.append({
                slack_utils.KEY_TITLE: 'Developer{}'.format(len(developers) > 1 and 's' or ''),
                slack_utils.KEY_TEXT: '\n\n'.join(
                    [
                        '*Name:* <{}|{}>\n'
                        '*Email:* {}'.format(
                            '{}/people/{}'.format(TUNGA_URL, user.username),
                            user.display_name,
                            user.email)

                        for user in developers
                    ]
                ),
                slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
                slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_RED
            })
    if not summary:
        summary = "New {} created by {} | <{}|View on Tunga>".format(
            task.scope == TASK_SCOPE_TASK and 'task' or 'project',
            task.user.display_name, task_url)

    return {
        slack_utils.KEY_TEXT: summary,
        slack_utils.KEY_CHANNEL: channel,
        slack_utils.KEY_ATTACHMENTS: attachments
    }


def create_task_stakeholders_attachment_slack(task, show_title=True):
    task_url = '{}/work/{}'.format(TUNGA_URL, task.id)
    owner = task.owner or task.user
    body_text = "*Project Owner:*\n" \
                " {} {}".format(owner.display_name, owner.email)

    if task.pm:
        body_text += "\n*Project Manager:*\n" \
                     "{} {} {}".format(
            task.pm.display_name,
            task.pm.email,
            task.pm.profile and task.pm.profile.phone_number and task.pm.profile.phone_number or ''
        )

    developers = task.active_participants
    if developers:
        body_text += "\n*Developer(s):*\n"
        body_text += '\n'.join(
            '{}. {} {} {}'.format(
                idx + 1,
                dev.display_name,
                dev.email,
                dev.profile and dev.profile.phone_number and dev.profile.phone_number or ''
            ) for idx, dev in enumerate(developers)
        )
    attachment = {
        slack_utils.KEY_TEXT: body_text,
        slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
        slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_BLUE
    }
    if show_title:
        attachment[slack_utils.KEY_TITLE] = task.summary
        attachment[slack_utils.KEY_TITLE_LINK] = task_url
    return attachment

@job
def notify_new_task_admin_slack(instance, new_user=False, completed=False, call_scheduled=False):
    instance = clean_instance(instance, Task)
    task_url = '{}/work/{}/'.format(TUNGA_URL, instance.id)

    completed_phrase = ''
    if call_scheduled:
        completed_phrase = 'availability window shared'
    elif completed:
        completed_phrase = 'details completed'

    summary = "{} {} {} by {}{} | <{}|View on Tunga>".format(
        (completed or call_scheduled) and 'New wizard' or 'New',
        instance.scope == TASK_SCOPE_TASK and 'task' or 'project',
        completed_phrase or 'created',
        instance.user.display_name, new_user and ' (New user)' or '',
        task_url
    )
    slack_msg = create_task_slack_msg(instance, summary=summary, channel=SLACK_STAFF_LEADS_CHANNEL, show_contacts=True, is_admin=True)
    slack_utils.send_incoming_webhook(SLACK_STAFF_INCOMING_WEBHOOK, slack_msg)


@job
def remind_no_task_applications_slack(instance, admin=True):
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
        channel=admin and SLACK_STAFF_LEADS_CHANNEL or SLACK_DEVELOPER_UPDATES_CHANNEL,
        show_contacts=admin
    )
    slack_utils.send_incoming_webhook(
        admin and SLACK_STAFF_INCOMING_WEBHOOK or SLACK_DEVELOPER_INCOMING_WEBHOOK,
        slack_msg
    )


@job
def notify_review_task_admin_slack(instance):
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
        channel=SLACK_STAFF_LEADS_CHANNEL,
        show_contacts=True
    )
    slack_utils.send_incoming_webhook(SLACK_STAFF_INCOMING_WEBHOOK, slack_msg)


@job
def notify_new_task_community_slack(instance):
    instance = clean_instance(instance, Task)

    # Notify Devs or PMs via Slack
    if (not instance.is_developer_ready) or (instance.approved and instance.visibility == VISIBILITY_DEVELOPER):
        slack_msg = create_task_slack_msg(
            instance,
            channel=instance.is_developer_ready and SLACK_DEVELOPER_UPDATES_CHANNEL or SLACK_PMS_UPDATES_CHANNEL
        )
        slack_utils.send_incoming_webhook(SLACK_DEVELOPER_INCOMING_WEBHOOK, slack_msg)


@job
def notify_task_invitation_response_slack(instance):
    instance = clean_instance(instance, Participation)

    if not slack_utils.is_task_notification_enabled(instance.task, slugs.EVENT_APPLICATION):
        return

    task_url = '%s/work/%s/' % (TUNGA_URL, instance.task_id)
    slack_msg = "Task invitation %s by %s %s\n\n<%s|View on Tunga>" % (
        instance.status == STATUS_ACCEPTED and 'accepted' or 'rejected', instance.user.short_name,
        instance.status == STATUS_ACCEPTED and ':smiley: :fireworks:' or ':unamused:',
        task_url
    )
    slack_utils.send_integration_message(instance.task, message=slack_msg)


@job
def notify_new_task_application_slack(instance, admin=True):
    instance = clean_instance(instance, Application)

    if not slack_utils.is_task_notification_enabled(instance.task, slugs.EVENT_APPLICATION):
        return

    application_url = '%s/work/%s/applications/' % (TUNGA_URL, instance.task_id)
    slack_msg = "New application from %s" % instance.user.short_name
    attachments = [
        {
            slack_utils.KEY_TITLE: instance.task.summary,
            slack_utils.KEY_TITLE_LINK: application_url,
            slack_utils.KEY_TEXT: '%s%s%s%s\n\n<%s|View on Tunga>' %
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
    if admin:
        slack_utils.send_incoming_webhook(
            SLACK_STAFF_INCOMING_WEBHOOK,
            {
                slack_utils.KEY_TEXT: slack_msg,
                slack_utils.KEY_ATTACHMENTS: attachments,
                slack_utils.KEY_CHANNEL: SLACK_STAFF_LEADS_CHANNEL
            }
        )
    else:
        slack_utils.send_integration_message(instance.task, message=slack_msg, attachments=attachments)


@job
def notify_task_application_response_slack(instance, admin=True):
    instance = clean_instance(instance, Application)

    application_url = '%s/work/%s/applications/' % (TUNGA_URL, instance.task_id)
    task_url = '%s/work/%s/' % (TUNGA_URL, instance.task.id)
    slack_msg = "Task Application {} | <{}|View on Tunga>".format(
        instance.status == STATUS_ACCEPTED and 'accepted' or 'rejected',
        task_url
    )

    attachments = [
        {
            slack_utils.KEY_TITLE: instance.task.summary,
            slack_utils.KEY_TITLE_LINK: application_url,
            slack_utils.KEY_TEXT: '%s%s%s%s\n\n<%s|View on Tunga>' %
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
    if admin:
        slack_utils.send_incoming_webhook(
            SLACK_STAFF_INCOMING_WEBHOOK,
            {
                slack_utils.KEY_TEXT: slack_msg,
                slack_utils.KEY_ATTACHMENTS: attachments,
                slack_utils.KEY_CHANNEL: SLACK_STAFF_LEADS_CHANNEL
            }
        )
    else:
        slack_utils.send_integration_message(instance.task, message=slack_msg, attachments=attachments)


@job
def remind_progress_event_slack(instance):
    instance = clean_instance(instance, ProgressEvent)

    task_integration = get_task_integration(instance.task, APP_INTEGRATION_PROVIDER_SLACK)
    if not task_integration:
        return

    is_pm_report = instance.type == PROGRESS_EVENT_TYPE_PM
    is_client_report = instance.type == PROGRESS_EVENT_TYPE_CLIENT
    is_pm_or_client_report = is_pm_report or is_client_report
    is_dev_report = not is_pm_or_client_report

    bot_access_token = task_integration.bot_access_token
    if not bot_access_token:
        if is_pm_report or is_dev_report:
            pass
            # TODO: set bot token to Tunga developers slack team token
        return

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

    slack_msg = "{} for \"{}\" | <{}|{} on Tunga>".format(
        is_client_report and "Weekly Survey" or "Upcoming {} Update".format(
            instance.task.is_task and 'Task' or 'Project'
        ),
        instance.task.summary,
        '{}/work/{}/event/{}/'.format(TUNGA_URL, instance.task.id, instance.id),
        is_client_report and "Take the survey" or "Give the update"
    )

    to_emails = []
    if is_pm_report:
        to_emails = [pm.email]

    elif is_client_report:
        to_emails = [owner.email]
        if owner.email != instance.task.user.email:
            to_emails.append(instance.task.user.email)

    else:
        participants = instance.task.participation_set.filter(status=STATUS_ACCEPTED)
        if participants:
            for participant in participants:
                to_emails.append(participant.user.email)

    if to_emails:
        for email in to_emails:
            im_id = get_user_im_id(email, bot_access_token)
            if im_id:
                slack_utils.send_slack_message(bot_access_token, im_id, message=slack_msg)


def create_progress_report_slack_message(instance, updated=False, to_client=False):
    is_pm_report = instance.event.type == PROGRESS_EVENT_TYPE_PM
    is_client_report = instance.event.type == PROGRESS_EVENT_TYPE_CLIENT
    is_pm_or_client_report = is_pm_report or is_client_report
    is_dev_report = not is_pm_or_client_report

    report_url = '%s/work/%s/event/%s/' % (TUNGA_URL, instance.event.task_id, instance.event_id)
    slack_msg = "{} {} a {} | {}".format(
        instance.user.display_name,
        updated and 'updated' or 'submitted',
        is_client_report and "Weekly Survey" or "Progress Report",
        '<{}|View on Tunga>'.format(report_url)
    )

    slack_text_suffix = ''
    if not is_client_report:
        slack_text_suffix += '*Status:* {}\n*Percentage completed:* {}{}'.format(
            instance.get_status_display(), instance.percentage, '%')
    if not to_client:
        if instance.last_deadline_met is not None:
            slack_text_suffix += '\n*Was the last deadline met?:* {}'.format(
                instance.last_deadline_met and 'Yes' or 'No'
            )
        if instance.next_deadline:
            slack_text_suffix += '\n*Next deadline:* {}'.format(instance.next_deadline.strftime("%d %b, %Y"))
    if is_client_report:
        if instance.deliverable_satisfaction is not None:
            slack_text_suffix += '\n*Are you satisfied with the deliverables?:* {}'.format(
                instance.deliverable_satisfaction and 'Yes' or 'No'
            )
    if is_dev_report:
        if instance.stuck_reason:
            slack_text_suffix += '\n*Reason for being stuck:*\n {}'.format(
                convert_to_text(instance.get_stuck_reason_display())
            )
    attachments = [
        {
            slack_utils.KEY_TITLE: instance.event.task.summary,
            slack_utils.KEY_TITLE_LINK: report_url,
            slack_utils.KEY_TEXT: slack_text_suffix,
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_BLUE
        }
    ]

    if not to_client:
        if instance.deadline_miss_communicated is not None:
            attachments.append({
                slack_utils.KEY_TITLE: '{} promptly about not making the deadline?'.format(
                    is_client_report and 'Did the project manager/ developer(s) inform you' or 'Did you inform the client'),
                slack_utils.KEY_TEXT: '{}'.format(instance.deadline_miss_communicated and 'Yes' or 'No'),
                slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
                slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_RED
            })

    if instance.deadline_report:
        attachments.append({
            slack_utils.KEY_TITLE: 'Report about the last deadline:',
            slack_utils.KEY_TEXT: convert_to_text(instance.deadline_report),
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_RED
        })

    if is_client_report:
        if instance.rate_deliverables:
            attachments.append({
                slack_utils.KEY_TITLE: 'How would you rate the deliverables on a scale from 1 to 5?',
                slack_utils.KEY_TEXT: '{}/5'.format(instance.rate_deliverables),
                slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
                slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_BLUE
            })
        if instance.pm_communication:
            attachments.append({
                slack_utils.KEY_TITLE: 'Is the communication between you and the project manager/developer(s) going well?',
                slack_utils.KEY_TEXT: '{}'.format(instance.pm_communication and 'Yes' or 'No'),
                slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
                slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_GREEN
            })
    else:
        # Status
        if instance.stuck_details:
            attachments.append({
                slack_utils.KEY_TITLE: 'Explain Further why you are stuck/what should be done:',
                slack_utils.KEY_TEXT: convert_to_text(instance.stuck_details),
                slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
                slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_GREEN
            })

        if instance.started_at and not to_client:
            attachments.append({
                slack_utils.KEY_TITLE: 'When did you start this sprint/task/project?',
                slack_utils.KEY_TEXT: instance.started_at.strftime("%d %b, %Y"),
                slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
                slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_BLUE
            })

        # Last
        if instance.accomplished:
            attachments.append({
                slack_utils.KEY_TITLE: 'What has been accomplished since last update?',
                slack_utils.KEY_TEXT: convert_to_text(instance.accomplished),
                slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
                slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_GREEN
            })
        if instance.rate_deliverables and not to_client:
            attachments.append({
                slack_utils.KEY_TITLE: 'Rate Deliverables:',
                slack_utils.KEY_TEXT: '{}/5'.format(instance.rate_deliverables),
                slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
                slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_RED
            })

        # Current
        if instance.todo:
            attachments.append({
                slack_utils.KEY_TITLE: is_dev_report and 'What do you intend to achieve/complete today?' or 'What are the next next steps?',
                slack_utils.KEY_TEXT: convert_to_text(instance.todo),
                slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
                slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_GREEN
            })

        if not to_client:
            # Next
            if instance.next_deadline:
                attachments.append({
                    slack_utils.KEY_TITLE: 'When is the next deadline?',
                    slack_utils.KEY_TEXT: instance.next_deadline.strftime("%d %b, %Y"),
                    slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
                    slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_RED
                })

            # Keep information about failures to meet deadlines internal
            if instance.next_deadline_meet is not None:
                attachments.append({
                    slack_utils.KEY_TITLE: 'Do you anticipate to meet this deadline?',
                    slack_utils.KEY_TEXT: '{}'.format(instance.next_deadline_meet and 'Yes' or 'No'),
                    slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
                    slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_GREEN
                })
            if instance.next_deadline_fail_reason:
                attachments.append({
                    slack_utils.KEY_TITLE: 'Why will you not be able to make the next deadline?',
                    slack_utils.KEY_TEXT: convert_to_text(instance.next_deadline_fail_reason),
                    slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
                    slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_RED
                })
        if instance.obstacles:
            attachments.append({
                slack_utils.KEY_TITLE: 'What obstacles are impeding your progress?',
                slack_utils.KEY_TEXT: convert_to_text(instance.obstacles),
                slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
                slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_RED
            })

    if is_pm_report:
        if instance.team_appraisal:
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

    return slack_msg, attachments


@job
def notify_new_progress_report_slack(instance, updated=False):
    instance = clean_instance(instance, ProgressReport)

    is_pm_report = instance.event.type == PROGRESS_EVENT_TYPE_PM
    is_client_report = instance.event.type == PROGRESS_EVENT_TYPE_CLIENT
    is_pm_or_client_report = is_pm_report or is_client_report
    is_dev_report = not is_pm_or_client_report

    #if not (slack_utils.is_task_notification_enabled(instance.event.task, slugs.EVENT_PROGRESS)):
    #    return

    # All reports go to Tunga #updates Slack
    slack_msg, attachments = create_progress_report_slack_message(instance, updated=updated)
    slack_utils.send_incoming_webhook(SLACK_STAFF_INCOMING_WEBHOOK, {
        slack_utils.KEY_TEXT: slack_msg,
        slack_utils.KEY_CHANNEL: SLACK_STAFF_UPDATES_CHANNEL,
        slack_utils.KEY_ATTACHMENTS: attachments
    })

    if is_dev_report:
        # Re-create report for clients
        slack_msg, attachments = create_progress_report_slack_message(instance, updated=updated, to_client=True)
        slack_utils.send_integration_message(instance.event.task, message=slack_msg, attachments=attachments)


@job
def notify_missed_progress_event_slack(instance):
    instance = clean_instance(instance, ProgressEvent)

    is_client_report = instance.type == PROGRESS_EVENT_TYPE_CLIENT

    if instance.status != "missed":
        return

    participants = instance.participants
    if not participants or instance.task.closed:
        # No one to report or task is now closed
        return

    target_user = None
    if participants and len(participants) == 1:
        target_user = participants[0]

    task_url = '{}/work/{}'.format(TUNGA_URL, instance.task.id)
    slack_msg = "`Alert (!):` {} {} for \"{}\" | <{}|View on Tunga>".format(
        target_user and '{} missed a'.format(target_user.short_name) or 'Missed',
        is_client_report and 'weekly survey' or 'progress report',
        instance.task.summary,
        task_url
    )

    attachments = [
        {
            slack_utils.KEY_TITLE: instance.task.summary,
            slack_utils.KEY_TITLE_LINK: task_url,
            slack_utils.KEY_TEXT: '\n\n'.join(
                [
                    '*Due Date:* {}\n\n'
                    '*Name:* {}\n'
                    '*Email:* {}{}'.format(
                        instance.due_at.strftime("%d %b, %Y"),
                        user.display_name,
                        user.email,
                        user.profile and user.profile.phone_number and '\n*Phone Number:* {}'.format(user.profile.phone_number) or ''
                    ) for user in participants
                ]
            ),
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_TUNGA
        }
    ]

    slack_utils.send_incoming_webhook(
        SLACK_STAFF_INCOMING_WEBHOOK,
        {
            slack_utils.KEY_TEXT: slack_msg,
            slack_utils.KEY_ATTACHMENTS: attachments,
            slack_utils.KEY_CHANNEL: SLACK_STAFF_UPDATES_CHANNEL
        }
    )

    # Save notification time
    instance.missed_notification_at = datetime.datetime.now()
    instance.save()


@job
def notify_progress_report_deadline_missed_slack_admin(instance):
    instance = clean_instance(instance, ProgressReport)

    task_url = '{}/work/{}'.format(TUNGA_URL, instance.event.task.id)
    slack_msg = "`Alert (!):` Follow up on missed deadline for \"{}\" | <{}|View on Tunga>".format(
        instance.event.task.summary,
        task_url
    )

    attachments = [
        {
            slack_utils.KEY_TITLE: instance.event.task.summary,
            slack_utils.KEY_TITLE_LINK: task_url,
            slack_utils.KEY_TEXT: 'A deadline has been missed on the "{}" {}\n'
                                  '*Was the client informed before hand?:* {}\n'
                                  'Please contact the stakeholders.'.format(
                instance.event.task.summary,
                instance.event.task.is_task and 'task' or 'project',
                instance.deadline_miss_communicated and 'Yes' or 'No'
            ),
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_TUNGA
        },
        create_task_stakeholders_attachment_slack(instance.event.task, show_title=False)
    ]

    slack_utils.send_incoming_webhook(
        SLACK_STAFF_INCOMING_WEBHOOK,
        {
            slack_utils.KEY_TEXT: slack_msg,
            slack_utils.KEY_ATTACHMENTS: attachments,
            slack_utils.KEY_CHANNEL: SLACK_STAFF_UPDATES_CHANNEL
        }
    )


@job
def notify_progress_report_behind_schedule_by_algo_slack_admin(instance):
    instance = clean_instance(instance, ProgressReport)

    task_url = '{}/work/{}'.format(TUNGA_URL, instance.event.task.id)
    slack_msg = "`Alert (!):` \"{}\" {} is running behind schedule | <{}|View on Tunga>".format(
        instance.event.task.summary,
        instance.event.task.is_task and 'task' or 'project',
        task_url
    )

    attachments = [
        {
            slack_utils.KEY_TITLE: instance.event.task.summary,
            slack_utils.KEY_TITLE_LINK: task_url,
            slack_utils.KEY_TEXT: 'Please contact the PM and devs.',
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_TUNGA
        },
        create_task_stakeholders_attachment_slack(instance.event.task, show_title=False)
    ]

    slack_utils.send_incoming_webhook(
        SLACK_STAFF_INCOMING_WEBHOOK,
        {
            slack_utils.KEY_TEXT: slack_msg,
            slack_utils.KEY_ATTACHMENTS: attachments,
            slack_utils.KEY_CHANNEL: SLACK_STAFF_UPDATES_CHANNEL
        }
    )


@job
def notify_progress_report_client_not_satisfied_slack_admin(instance):
    instance = clean_instance(instance, ProgressReport)

    task_url = '{}/work/{}/event/{}'.format(TUNGA_URL, instance.event.task.id, instance.event.id)
    slack_msg = "`Alert (!):` Client dissatisfied | <{}|View on Tunga>".format(task_url)

    attachments = [
        {
            slack_utils.KEY_TITLE: instance.event.task.summary,
            slack_utils.KEY_TITLE_LINK: task_url,
            slack_utils.KEY_TEXT: 'The project owner of \"{}\" {} is unsatisfied with the deliverable.\n '
                                  'Please contact all stakeholders.'.format(
                instance.event.task.summary,
                instance.event.task.is_task and 'task' or 'project'
            ),
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_TUNGA
        },
        create_task_stakeholders_attachment_slack(instance.event.task, show_title=False)
    ]

    slack_utils.send_incoming_webhook(
        SLACK_STAFF_INCOMING_WEBHOOK,
        {
            slack_utils.KEY_TEXT: slack_msg,
            slack_utils.KEY_ATTACHMENTS: attachments,
            slack_utils.KEY_CHANNEL: SLACK_STAFF_UPDATES_CHANNEL
        }
    )


@job
def notify_progress_report_stuck_slack_admin(instance):
    instance = clean_instance(instance, ProgressReport)

    task_url = '{}/work/{}/event/{}'.format(TUNGA_URL, instance.event.task.id, instance.event.id)
    slack_msg = "`Alert (!):` The status for the \"{}\" {} has been classified as stuck | <{}|View on Tunga>".format(
        instance.event.task.summary,
        instance.event.task.is_task and 'task' or 'project',
        task_url
    )

    attachments = [
        {
            slack_utils.KEY_TITLE: instance.event.task.summary,
            slack_utils.KEY_TITLE_LINK: task_url,
            slack_utils.KEY_TEXT: 'Please contact all stakeholders.',
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_TUNGA
        },
        create_task_stakeholders_attachment_slack(instance.event.task, show_title=False)
    ]

    slack_utils.send_incoming_webhook(
        SLACK_STAFF_INCOMING_WEBHOOK,
        {
            slack_utils.KEY_TEXT: slack_msg,
            slack_utils.KEY_ATTACHMENTS: attachments,
            slack_utils.KEY_CHANNEL: SLACK_STAFF_UPDATES_CHANNEL
        }
    )


@job
def notify_progress_report_wont_meet_deadline_slack_admin(instance):
    instance = clean_instance(instance, ProgressReport)

    task_url = '{}/work/{}/event/{}'.format(TUNGA_URL, instance.event.task.id, instance.event.id)
    slack_msg = "`Alert (!):` {} doesn't expect to meet the deadline | <{}|View on Tunga>".format(
        instance.event.type == PROGRESS_EVENT_TYPE_PM and 'PM' or 'Developer',
        task_url
    )

    attachments = [
        {
            slack_utils.KEY_TITLE: instance.event.task.summary,
            slack_utils.KEY_TITLE_LINK: task_url,
            slack_utils.KEY_TEXT: 'The {} on the \"{}\" {} has indicated that they might not meet the coming deadline.\n'
                                  'Please contact all stakeholders.'.format(
                instance.event.type == PROGRESS_EVENT_TYPE_PM and 'PM' or 'Developer',
                instance.event.task.summary,
                instance.event.task.is_task and 'task' or 'project'
            ),
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_TUNGA
        },
        create_task_stakeholders_attachment_slack(instance.event.task, show_title=False)
    ]

    slack_utils.send_incoming_webhook(
        SLACK_STAFF_INCOMING_WEBHOOK,
        {
            slack_utils.KEY_TEXT: slack_msg,
            slack_utils.KEY_ATTACHMENTS: attachments,
            slack_utils.KEY_CHANNEL: SLACK_STAFF_UPDATES_CHANNEL
        }
    )


@job
def send_survey_summary_report_slack(event, client_report, pm_report, dev_report):
    event = clean_instance(event, ProgressEvent)
    client_report = clean_instance(client_report, ProgressReport)
    pm_report = clean_instance(pm_report, ProgressReport)
    dev_report = clean_instance(dev_report, ProgressReport)

    print('client reports: ', client_report)
    print('pm report: ', pm_report)
    print('dev report: ', dev_report)

    # Notify via Slack of sent email to double check and prevent multiple sends

    attachments = list()
    if not client_report:
        attachments.append({
            slack_utils.KEY_TEXT: '`Client survey was not filled`',
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_RED,
        })

    if event.task.pm and not pm_report:
        attachments.append({
            slack_utils.KEY_TEXT: '`PM Report was not filled`',
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_RED,
        })

    if event.task.active_participants and not dev_report:
        attachments.append({
            slack_utils.KEY_TEXT: '`No Developer report was filled`',
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_RED,
        })
    if client_report or pm_report or dev_report:
        if client_report:
            summary_report = list()
            summary_report.append(dict(
                title='Was the last deadline met?:',
                client=client_report and (client_report.last_deadline_met and 'Yes' or 'No') or None,
                pm=pm_report and (pm_report.last_deadline_met and 'Yes' or 'No') or None,
                dev=dev_report and (dev_report.last_deadline_met and 'Yes' or 'No') or None,
                color=client_report.last_deadline_met and SLACK_ATTACHMENT_COLOR_GREEN or SLACK_ATTACHMENT_COLOR_RED
            ))

            if not client_report.last_deadline_met:
                summary_report.append(dict(
                    title='Was the client informed about missing the deadline?:',
                    client=(client_report.deadline_miss_communicated and 'Yes' or 'No') or None,
                    pm=pm_report and (pm_report.deadline_miss_communicated and 'Yes' or 'No') or None,
                    dev=dev_report and (dev_report.deadline_miss_communicated and 'Yes' or 'No') or None,
                    color=client_report.deadline_miss_communicated and SLACK_ATTACHMENT_COLOR_GREEN or SLACK_ATTACHMENT_COLOR_RED
                ))

            if client_report.deliverable_satisfaction is not None:
                summary_report.append(dict(
                    title='Are you satisfied with the deliverable?:',
                    client=(client_report.deliverable_satisfaction and 'Yes' or 'No') or None,
                    pm=None,
                    dev=None,
                    color=client_report.deliverable_satisfaction and SLACK_ATTACHMENT_COLOR_GREEN or SLACK_ATTACHMENT_COLOR_RED
                ))

            if client_report.rate_deliverables is not None:
                summary_report.append(dict(
                    title='Deliverable rating:',
                    client=client_report.rate_deliverables or None,
                    pm=pm_report and pm_report.rate_deliverables or None,
                    dev=dev_report and dev_report.rate_deliverables or None,
                    color=(client_report.rate_deliverables > 3 and SLACK_ATTACHMENT_COLOR_GREEN) or (client_report.rate_deliverables < 3 and SLACK_ATTACHMENT_COLOR_RED or SLACK_ATTACHMENT_COLOR_NEUTRAL)
                ))

            if pm_report or dev_report:
                summary_report.append(dict(
                    title='Status:',
                    client=None,
                    pm=pm_report and pm_report.get_status_display() or None,
                    dev=dev_report and dev_report.get_status_display() or None,
                    color=SLACK_ATTACHMENT_COLOR_RED
                ))

                if (pm_report and pm_report.stuck_reason) or (dev_report and dev_report.stuck_reason):
                    summary_report.append(dict(
                        title='Stuck reason:',
                        client=None,
                        pm=pm_report and pm_report.get_stuck_reason_display() or None,
                        dev=dev_report and dev_report.get_stuck_reason_display() or None,
                        color=SLACK_ATTACHMENT_COLOR_BLUE
                    ))

            for item in summary_report:
                client = item.get('client', None)
                pm = item.get('pm', None)
                dev = item.get('dev', None)
                attachments.append({
                    slack_utils.KEY_TITLE: item['title'],
                    slack_utils.KEY_TEXT: '{} {} {}'.format(
                        client and 'Client: {}'.format(client) or '',
                        pm and '{}PM: {}{}'.format(
                            client_report and '*|* ' or '', pm, dev_report and ' *|*' or ''
                        ) or '{}'.format(dev_report and '*|*' or ''),
                        dev and 'Dev: {}'.format(dev) or ''),
                    slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
                    slack_utils.KEY_COLOR: item.get('color', SLACK_ATTACHMENT_COLOR_NEUTRAL)
                })
        else:
            attachments.append({
                slack_utils.KEY_TEXT: '`Insufficent data for creating a summary report`',
                slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
                slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_RED,
            })

        attachments.append({
            slack_utils.KEY_TITLE: 'Reports:',
            slack_utils.KEY_TEXT: '{}{}{}'.format(
                client_report and '<{}|Client Survey>'.format('{}/work/{}/event/{}'.format(TUNGA_URL, event.task.id, client_report.event.id)) or '',
                pm_report and '{}<{}|PM Report>{}'.format(client_report and '\n' or '', '{}/work/{}/event/{}'.format(TUNGA_URL, event.task.id, pm_report.event.id), dev_report and '\n' or '') or '{}'.format(dev_report and '\n' or ''),
                dev_report and '<{}|Developer Report>'.format('{}/work/{}/event/{}'.format(TUNGA_URL, event.task.id, dev_report.event.id)) or '',
            ),
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_BLUE,
        })

    owner = event.task.owner or event.task.user

    slack_utils.send_incoming_webhook(
        SLACK_STAFF_INCOMING_WEBHOOK,
        {
            slack_utils.KEY_TEXT: "*Summary Report:* <{}|{}>\nProject Owner: <{}|{}>{}".format(
                '{}/work/{}'.format(TUNGA_URL, event.task.id), event.task.summary,
                '{}/people/{}'.format(TUNGA_URL, owner.username), owner.display_name,
                event.task.pm and '\nPM: <{}|{}>'.format('{}/people/{}'.format(
                    TUNGA_URL, event.task.pm.username), event.task.pm.display_name
                ) or ''
            ),
            slack_utils.KEY_CHANNEL: SLACK_STAFF_PROJECT_EXECUTION_CHANNEL,
            slack_utils.KEY_ATTACHMENTS: attachments
        }
    )


@job
def notify_new_task_invoice_admin_slack(instance):
    instance = clean_instance(instance, TaskInvoice)

    task_url = '{}/work/{}/'.format(TUNGA_URL, instance.task.id)
    owner = instance.task.owner or instance.task.user
    client_url = '{}/people/{}/'.format(TUNGA_URL, owner.username)
    invoice_url = '{}/api/task/{}/download/invoice/?format=pdf'.format(TUNGA_URL, instance.task.id)
    slack_msg = '{} generated an invoice'.format(
        instance.user.display_name
    )

    attachments = [
        {
            slack_utils.KEY_TITLE: instance.task.summary,
            slack_utils.KEY_TITLE_LINK: task_url,
            slack_utils.KEY_TEXT: 'Client: <{}|{}>\nFee: {}\nPayment Method: {}\n<{}|Download invoice>'.format(
                client_url,
                owner.display_name,
                instance.display_fee().encode('utf-8'),
                instance.get_payment_method_display(),
                invoice_url
            ),
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_BLUE
        },
    ]
    if not instance.task.payment_approved:
        if instance.payment_method == TASK_PAYMENT_METHOD_BANK:
            attachments.append({
                slack_utils.KEY_TITLE: 'No payment approval required.',
                slack_utils.KEY_TEXT: 'Payment will be completed via bank transfer.',
                slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
                slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_GREEN
            })
        else:
            task_approval_url = '{}edit/payment-approval/'.format(task_url)
            attachments.append({
                slack_utils.KEY_TITLE: 'Review and approve payment.',
                slack_utils.KEY_TITLE_LINK: task_approval_url,
                slack_utils.KEY_TEXT: "The client won't be able to pay until the payment is approved.",
                slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT],
                slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_RED
            })

    slack_utils.send_incoming_webhook(
        SLACK_STAFF_INCOMING_WEBHOOK,
        {
            slack_utils.KEY_TEXT: slack_msg,
            slack_utils.KEY_ATTACHMENTS: attachments,
            slack_utils.KEY_CHANNEL: SLACK_STAFF_PAYMENTS_CHANNEL
        }
    )
