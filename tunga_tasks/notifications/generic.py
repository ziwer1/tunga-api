import time

from django_rq import job

from tunga.settings import MAILCHIMP_NEW_USER_AUTOMATION_WORKFLOW_ID, MAILCHIMP_NEW_USER_AUTOMATION_EMAIL_ID
from tunga_tasks.models import Task
from tunga_tasks.notifications.email import notify_new_task_client_receipt_email, notify_new_task_admin_email, \
    notify_new_task_community_email, notify_task_invitation_response_email, notify_new_task_application_owner_email, \
    confirm_task_application_to_applicant_email, notify_task_application_response_owner_email, \
    notify_task_application_response_admin_email, remind_progress_event_email, notify_new_progress_report_email
from tunga_tasks.notifications.slack import notify_new_task_admin_slack, remind_no_task_applications_slack, \
    notify_review_task_admin_slack, notify_new_task_community_slack, notify_task_invitation_response_slack, \
    notify_new_task_application_slack, notify_task_application_response_slack, remind_progress_event_slack, \
    notify_missed_progress_event_slack, notify_new_progress_report_slack
from tunga_utils import mailchimp_utils
from tunga_utils.helpers import clean_instance


@job
def possibly_trigger_schedule_call_automation(instance, wait=15*60):
    # Wait for user to possibly schedule a call
    time.sleep(wait)

    instance = clean_instance(isinstance(instance, Task) and instance.id or instance, Task)  # needs to be refreshed
    if not instance.schedule_call_start:
        # Make sure user is in mailing list
        mailchimp_utils.subscribe_new_user(
            instance.user.email, **dict(FNAME=instance.user.first_name, LNAME=instance.user.last_name)
        )

        # Trigger email from automation
        mailchimp_utils.add_email_to_automation_queue(
            email_address=instance.user.email,
            workflow_id=MAILCHIMP_NEW_USER_AUTOMATION_WORKFLOW_ID,
            email_id=MAILCHIMP_NEW_USER_AUTOMATION_EMAIL_ID
        )


@job
def notify_new_task(instance, new_user=False):
    notify_new_task_client_receipt_email(instance)

    if not new_user:
        # Task from new users need to be qualified before they get to the community
        notify_new_task_community(instance)

    notify_new_task_admin(instance, new_user=new_user)


@job
def notify_task_approved(instance, new_user=False):
    notify_new_task_client_receipt_email(instance)
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
    confirm_task_application_to_applicant_email.delay(instance.id)

    # Notify admins
    notify_new_task_application_slack.delay(instance.id, admin=True)


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