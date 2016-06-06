from django.contrib.auth import get_user_model
from django.core.mail.message import EmailMessage
from django.db.models.query_utils import Q
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver
from django.template.loader import render_to_string

from tunga.settings import DEFAULT_FROM_EMAIL, EMAIL_SUBJECT_PREFIX
from tunga_messages.emails import send_new_message_email, send_new_reply_email
from tunga_messages.models import Message, Reply, Reception


@receiver(post_save, sender=Message)
def activity_handler_new_message(sender, instance, created, **kwargs):
    if created:
        send_new_message_email(instance)


@receiver(post_save, sender=Reception)
def activity_handler_new_message_recipient(sender, instance, created, **kwargs):
    if created:
        send_new_message_email(instance.message, to=[instance.user.email])


@receiver(post_save, sender=Reply)
def activity_handler_new_reply(sender, instance, created, **kwargs):
    if created:
        send_new_reply_email(instance)
