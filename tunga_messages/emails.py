from django_rq.decorators import job

from tunga.settings import EMAIL_SUBJECT_PREFIX, TUNGA_URL
from tunga_messages.models import Message
from tunga_settings.slugs import DIRECT_MESSAGES_EMAIL
from tunga_utils.decorators import clean_instance
from tunga_utils.emails import send_mail


@job
def send_new_message_email(instance):
    instance = clean_instance(instance, Message)
    to = []
    recipients = instance.channel.participants.exclude(id=instance.user.id).exclude(
        userswitchsetting__setting__slug=DIRECT_MESSAGES_EMAIL,
        userswitchsetting__value=False
    )
    if recipients:
        to = [recipient.email for recipient in recipients]
    if to and isinstance(to, (list, tuple)):
        subject = "%s New message from %s" % (EMAIL_SUBJECT_PREFIX, instance.user.first_name)
        ctx = {
            'sender': instance.user.first_name,
            'subject': instance.channel.subject,
            'channel': instance.channel,
            'message': instance,
            'message_url': '%s/channel/%s/' % (TUNGA_URL, instance.channel.id)
        }
        send_mail(subject, 'tunga/email/email_new_message', to, ctx)
