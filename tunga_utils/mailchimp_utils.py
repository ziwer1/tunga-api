from mailchimp3 import MailChimp

from tunga.settings import MAILCHIMP_USERNAME, MAILCHIMP_API_KEY, MAILCHIMP_NEW_USER_LIST


def get_client():
    return MailChimp(MAILCHIMP_USERNAME, MAILCHIMP_API_KEY)


def subscribe_new_user(email, **kwargs):
    client = get_client()
    client.lists.members.create(MAILCHIMP_NEW_USER_LIST, {
        'email_address': email,
        'status': 'subscribed',
        'merge_fields': kwargs
    })


def add_email_to_automation_queue(email_address, workflow_id, email_id, **kwargs):
    client = get_client()
    client.automations.emails.queues.create(workflow_id=workflow_id, email_id=email_id, data={
        'email_address': email_address,
        #'status': 'subscribed',
        'merge_fields': kwargs
    })
