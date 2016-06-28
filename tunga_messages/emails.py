from django.contrib.auth import get_user_model
from django.db.models.query_utils import Q

from tunga.settings import EMAIL_SUBJECT_PREFIX, TUNGA_URL
from tunga_utils.decorators import catch_all_exceptions
from tunga_utils.emails import send_mail


@catch_all_exceptions
def send_new_message_email(instance):
    to = []
    recipients = instance.channel.participants.exclude(id=instance.user.id)
    if recipients:
        to = [recipient.email for recipient in recipients]
    if to and isinstance(to, (list, tuple)):
        subject = "%s New message from %s" % (EMAIL_SUBJECT_PREFIX, instance.user.first_name)
        ctx = {
            'sender': instance.user.first_name,
            'subject': instance.channel.subject,
            'channel': instance.channel,
            'message': instance,
            'message_url': '%s/message/%s/' % (TUNGA_URL, instance.channel.id)
        }
        send_mail(subject, 'tunga/email/email_new_message', to, ctx)

