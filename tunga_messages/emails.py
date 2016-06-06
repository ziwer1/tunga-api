from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage
from django.db.models.query_utils import Q
from django.template.loader import render_to_string

from tunga.settings import EMAIL_SUBJECT_PREFIX
from tunga.settings.base import TUNGA_URL
from tunga_utils.decorators import catch_all_exceptions


@catch_all_exceptions
def send_new_message_email(instance, to=None):
    if not to:
        if instance.is_broadcast:
            recipients = get_user_model().objects.filter(
                (
                    Q(connections_initiated__accepted=True) &
                    Q(connections_initiated__to_user=instance.user)
                ) |
                (
                    Q(connection_requests__from_user=instance.user) &
                    Q(connection_requests__accepted=True)
                )
            )
        else:
            recipients = instance.recipients.all()
        if recipients:
            to = [recipient.email for recipient in recipients]
    if to and isinstance(to, (list, tuple)):
        subject = "%s New message from %s" % (EMAIL_SUBJECT_PREFIX, instance.user.first_name)
        message = render_to_string(
            'tunga/email/email_new_message.txt',
            {
                'sender': instance.user.first_name,
                'subject': instance.subject,
                'message': instance.body,
                'message_url': '%s/message/%s/' % (TUNGA_URL, instance.id)
            }
        )
        EmailMessage(subject, message, to=to).send()


@catch_all_exceptions
def send_new_reply_email(instance):
    recipients = []
    if instance.is_broadcast:
        recipients = list(instance.message.recipients.exclude(id=instance.user.id))
    if instance.message.user != instance.user:
        recipients.append(instance.message.user)
    if recipients:
        subject = "%s New message from %s" % (EMAIL_SUBJECT_PREFIX, instance.user.first_name)
        to = [recipient.email for recipient in recipients]

        message = render_to_string(
            'tunga/email/email_new_message.txt',
            {
                'sender': instance.user.first_name,
                'subject': instance.message.subject,
                'message': instance.body,
                'message_url': '%s/message/%s/' % (TUNGA_URL, instance.message.id)
            }
        )
        EmailMessage(subject, message, to=to).send()
