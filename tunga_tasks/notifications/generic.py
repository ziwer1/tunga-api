# -*- coding: utf-8 -*-

import datetime

from django_rq import job

from tunga_tasks.models import ProgressReport
from tunga_tasks.notifications.email import notify_new_task_client_receipt_email, notify_new_task_admin_email, \
    notify_new_task_community_email, notify_task_invitation_response_email, notify_new_task_application_owner_email, \
    confirm_task_application_to_applicant_email, notify_task_application_response_owner_email, \
    notify_task_application_response_admin_email, remind_progress_event_email, notify_new_progress_report_email, \
    notify_progress_report_deadline_missed_email_client, \
    notify_progress_report_deadline_missed_email_pm, notify_progress_report_deadline_missed_email_dev, \
    notify_progress_report_deadline_missed_email_admin, notify_progress_report_behind_schedule_by_algo_email_admin, \
    notify_progress_report_behind_schedule_by_algo_email_pm, notify_progress_report_behind_schedule_by_algo_email_dev, \
    notify_progress_report_client_not_satisfied_email_admin, notify_progress_report_client_not_satisfied_email_client, \
    notify_progress_report_client_not_satisfied_email_pm, notify_progress_report_client_not_satisfied_email_dev, \
    notify_progress_report_stuck_email_admin, notify_progress_report_stuck_email_pm, \
    notify_progress_report_stuck_email_dev, notify_progress_report_wont_meet_deadline_email_admin, \
    notify_progress_report_wont_meet_deadline_email_pm, notify_progress_report_wont_meet_deadline_email_dev, \
    notify_new_task_invoice_admin_email, notify_new_task_invoice_client_email
from tunga_tasks.notifications.slack import notify_new_task_admin_slack, remind_no_task_applications_slack, \
    notify_review_task_admin_slack, notify_new_task_community_slack, notify_task_invitation_response_slack, \
    notify_new_task_application_slack, notify_task_application_response_slack, remind_progress_event_slack, \
    notify_missed_progress_event_slack, notify_new_progress_report_slack, \
    notify_progress_report_deadline_missed_slack_admin, notify_progress_report_behind_schedule_by_algo_slack_admin, \
    notify_progress_report_client_not_satisfied_slack_admin, notify_progress_report_stuck_slack_admin, \
    notify_progress_report_wont_meet_deadline_slack_admin, send_survey_summary_report_slack, \
    notify_new_task_invoice_admin_slack
from tunga_utils.constants import PROGRESS_EVENT_TYPE_PM, PROGRESS_EVENT_TYPE_CLIENT, PROGRESS_REPORT_STATUS_STUCK, \
    PROGRESS_REPORT_STATUS_BEHIND_AND_STUCK
from tunga_utils.helpers import clean_instance


@job
def notify_new_task(instance, new_user=False):
    notify_new_task_client_receipt_email(instance)

    if not new_user:
        # Task from new users need to be qualified before they get to the community
        notify_new_task_community(instance)

    notify_new_task_admin(instance, new_user=new_user)


@job
def notify_task_approved(instance, new_user=False):
    # notify_new_task_client_receipt_email(instance)
    notify_new_task_admin(instance, new_user=new_user, completed=True)
    notify_new_task_community(instance)


@job
def notify_new_task_admin(instance, new_user=False, completed=False, call_scheduled=False):
    notify_new_task_admin_slack(instance, new_user=new_user, completed=completed, call_scheduled=call_scheduled)
    if not (completed or call_scheduled):
        # Only initial task creation will be reported via email
        notify_new_task_admin_email(instance, new_user=new_user, completed=completed, call_scheduled=call_scheduled)


@job
def remind_no_task_applications(instance, admin=True):
    remind_no_task_applications_slack(instance, admin=admin)


@job
def notify_review_task_admin(instance):
    notify_review_task_admin_slack(instance)


@job
def notify_new_task_community(instance):
    notify_new_task_community_email(instance)
    notify_new_task_community_slack(instance)


@job
def notify_task_invitation_response(instance):
    notify_task_invitation_response_email(instance)
    notify_task_invitation_response_slack(instance)


@job
def notify_new_task_application(instance):
    # Notify project owner
    notify_new_task_application_owner_email(instance)
    notify_new_task_application_slack(instance, admin=False)

    # Send email confirmation to applicant
    confirm_task_application_to_applicant_email.delay(instance)

    # Notify admins
    notify_new_task_application_slack.delay(instance, admin=True)


@job
def notify_task_application_response(instance):
    # Notify owner
    notify_task_application_response_owner_email(instance)

    # Notify admins
    notify_task_application_response_admin_email(instance)
    notify_task_application_response_slack(instance, admin=True)


@job
def remind_progress_event(instance):
    remind_progress_event_email(instance)
    remind_progress_event_slack(instance)


@job
def notify_missed_progress_event(instance):
    notify_missed_progress_event_slack(instance)


@job
def notify_new_progress_report(instance):
    notify_new_progress_report_email(instance)
    notify_new_progress_report_slack(instance)

    # trigger_progress_report_actionable_events(instance)


@job
def trigger_progress_report_actionable_events(instance):
    # Trigger actionable event notifications
    instance = clean_instance(instance, ProgressReport)
    is_pm_report = instance.event.type == PROGRESS_EVENT_TYPE_PM
    is_client_report = instance.event.type == PROGRESS_EVENT_TYPE_CLIENT
    is_pm_or_client_report = is_pm_report or is_client_report
    is_dev_report = not is_pm_or_client_report

    task = instance.event.task
    has_pm = instance.event.task.pm

    # Deadline wasn't met
    if instance.last_deadline_met is not None and not instance.last_deadline_met:
        if is_pm_report or is_dev_report:
            notify_progress_report_deadline_missed_admin(instance)

            notify_progress_report_deadline_missed_client(instance)

            if has_pm:
                notify_progress_report_deadline_missed_pm(instance)

            if is_dev_report:
                notify_progress_report_deadline_missed_dev(instance)

    # More than 20% difference between time passed and accomplished
    if task.deadline:
        if is_dev_report and instance.started_at and task.deadline > instance.started_at:
            right_now = datetime.datetime.utcnow()
            spent_percentage = ((right_now - instance.started_at)/(task.deadline - right_now))*100
            if ((instance.percentage or 0) + 20) < spent_percentage:
                notify_progress_report_behind_schedule_by_algo_admin(instance)

                if has_pm:
                    notify_progress_report_behind_schedule_by_algo_pm(instance)

                notify_progress_report_behind_schedule_by_algo_dev(instance)

    # Client not satisfied with deliverable
    if instance.deliverable_satisfaction is not None and not instance.deliverable_satisfaction:
        if is_client_report:
            notify_progress_report_client_not_satisfied_admin(instance)

            notify_progress_report_client_not_satisfied_client(instance)

            if has_pm:
                notify_progress_report_client_not_satisfied_pm(instance)

            notify_progress_report_client_not_satisfied_dev(instance)

    # Stuck and/ or not progressing
    if instance.status in [PROGRESS_REPORT_STATUS_STUCK, PROGRESS_REPORT_STATUS_BEHIND_AND_STUCK]:
        if is_pm_report or is_dev_report:
            notify_progress_report_stuck_admin(instance)

            if has_pm:
                notify_progress_report_stuck_pm(instance)

            if is_dev_report:
                notify_progress_report_stuck_dev(instance)


# Deadline missed
@job
def notify_progress_report_deadline_missed_admin(instance):
    notify_progress_report_deadline_missed_slack_admin(instance)
    notify_progress_report_deadline_missed_email_admin(instance)


@job
def notify_progress_report_deadline_missed_client(instance):
    notify_progress_report_deadline_missed_email_client(instance)


@job
def notify_progress_report_deadline_missed_pm(instance):
    notify_progress_report_deadline_missed_email_pm(instance)


@job
def notify_progress_report_deadline_missed_dev(instance):
    notify_progress_report_deadline_missed_email_dev(instance)


# More than 20% difference in time spent and accomplished
@job
def notify_progress_report_behind_schedule_by_algo_admin(instance):
    notify_progress_report_behind_schedule_by_algo_slack_admin(instance)
    notify_progress_report_behind_schedule_by_algo_email_admin(instance)


@job
def notify_progress_report_behind_schedule_by_algo_pm(instance):
    notify_progress_report_behind_schedule_by_algo_email_pm(instance)


@job
def notify_progress_report_behind_schedule_by_algo_dev(instance):
    notify_progress_report_behind_schedule_by_algo_email_dev(instance)


# Client not satisfied with deliverable
@job
def notify_progress_report_client_not_satisfied_admin(instance):
    notify_progress_report_client_not_satisfied_slack_admin(instance)
    notify_progress_report_client_not_satisfied_email_admin(instance)


@job
def notify_progress_report_client_not_satisfied_client(instance):
    notify_progress_report_client_not_satisfied_email_client(instance)


@job
def notify_progress_report_client_not_satisfied_pm(instance):
    notify_progress_report_client_not_satisfied_email_pm(instance)


@job
def notify_progress_report_client_not_satisfied_dev(instance):
    notify_progress_report_client_not_satisfied_email_dev(instance)


# Stuck and/ or not progressing
@job
def notify_progress_report_stuck_admin(instance):
    notify_progress_report_stuck_slack_admin(instance)
    notify_progress_report_stuck_email_admin(instance)


@job
def notify_progress_report_stuck_pm(instance):
    notify_progress_report_stuck_email_pm(instance)


@job
def notify_progress_report_stuck_dev(instance):
    notify_progress_report_stuck_email_dev(instance)


# Won't meet deadline
@job
def notify_progress_report_wont_meet_deadline_admin(instance):
    notify_progress_report_wont_meet_deadline_slack_admin(instance)
    notify_progress_report_wont_meet_deadline_email_admin(instance)


@job
def notify_progress_report_wont_meet_deadline_pm(instance):
    notify_progress_report_wont_meet_deadline_email_pm(instance)


@job
def notify_progress_report_wont_meet_deadline_dev(instance):
    notify_progress_report_wont_meet_deadline_email_dev(instance)


@job
def send_survey_summary_report(event, client_report, pm_report, dev_report):
    send_survey_summary_report_slack(event, client_report, pm_report, dev_report)


@job
def notify_new_task_invoice(instance):
    notify_new_task_invoice_client_email.delay(instance)
    notify_new_task_invoice_admin_slack.delay(instance)
    notify_new_task_invoice_admin_email.delay(instance)
