import hashlib

from mailchimp3 import MailChimp

from tunga.settings import MAILCHIMP_USERNAME, MAILCHIMP_API_KEY, MAILCHIMP_NEW_USER_LIST


def get_client():
    return MailChimp(MAILCHIMP_USERNAME, MAILCHIMP_API_KEY)


def subscribe_new_user(email, **kwargs):
    client = get_client()
    client.lists.members.create_or_update(
        list_id=MAILCHIMP_NEW_USER_LIST,
        subscriber_hash=hashlib.md5(email).hexdigest(),
        data={
            'email_address': email,
            'status_if_new': 'subscribed',
            'merge_fields': kwargs
        }
    )


def add_email_to_automation_queue(email_address, workflow_id, email_id):
    client = get_client()
    client.automations.emails.queues.create(workflow_id=workflow_id, email_id=email_id, data={
        'email_address': email_address
    })
