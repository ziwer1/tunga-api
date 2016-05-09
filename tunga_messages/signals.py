from django.contrib.auth import get_user_model
from django.core.mail.message import EmailMessage
from django.db.models.query_utils import Q
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver
from django.template.loader import render_to_string

from tunga.settings import DEFAULT_FROM_EMAIL, EMAIL_SUBJECT_PREFIX
from tunga_messages.models import Message, Reply, Reception


@receiver(post_save, sender=Message)
def activity_handler_new_message(sender, instance, created, **kwargs):
    if created:
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
            subject = "%s New message from %s" % (EMAIL_SUBJECT_PREFIX, instance.user.first_name)
            to = [recipient.email for recipient in recipients]
            from_email = DEFAULT_FROM_EMAIL

            message = render_to_string(
                'tunga/email/email_new_message.txt',
                {
                    'sender': instance.user.first_name,
                    'subject': instance.subject,
                    'message': instance.body,
                    'message_url': 'http://tunga.io/message/%s/' % instance.id
                }
            )
            EmailMessage(subject, message, to=to, from_email=from_email).send()


@receiver(post_save, sender=Reception)
def activity_handler_new_message_recipient(sender, instance, created, **kwargs):
    if created:
        subject = "%s New message from %s" % (EMAIL_SUBJECT_PREFIX, instance.message.user.first_name)
        to = [instance.user.email]
        from_email = DEFAULT_FROM_EMAIL

        message = render_to_string(
            'tunga/email/email_new_message.txt',
            {
                'sender': instance.message.user.first_name,
                'subject': instance.message.subject,
                'message': instance.message.body,
                'message_url': 'http://tunga.io/message/%s/' % instance.message.id
            }
        )
        EmailMessage(subject, message, to=to, from_email=from_email).send()



@receiver(post_save, sender=Reply)
def activity_handler_new_reply(sender, instance, created, **kwargs):
    if created:
        recipients = []
        if instance.is_broadcast:
            recipients = list(instance.message.recipients.exclude(id=instance.user.id))
        if instance.message.user != instance.user:
            recipients.append(instance.message.user)
        if recipients:
            subject = "%s New message from %s" % (EMAIL_SUBJECT_PREFIX, instance.user.first_name)
            to = [recipient.email for recipient in recipients]
            from_email = DEFAULT_FROM_EMAIL

            message = render_to_string(
                'tunga/email/email_new_message.txt',
                {
                    'sender': instance.user.first_name,
                    'subject': instance.message.subject,
                    'message': instance.body,
                    'message_url': 'http://tunga.io/message/%s/' % instance.message.id
                }
            )
            EmailMessage(subject, message, to=to, from_email=from_email).send()
