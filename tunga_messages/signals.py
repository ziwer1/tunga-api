from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver

from tunga_messages.emails import send_new_message_email
from tunga_messages.models import Message, Channel, CHANNEL_TYPE_DIRECT, CHANNEL_TYPE_TOPIC, ChannelUser
from tunga_messages.tasks import clean_direct_channel


@receiver(post_save, sender=Channel)
def activity_handler_channel(sender, instance, created, **kwargs):
    if instance.type == CHANNEL_TYPE_DIRECT:
        clean_direct_channel(instance)


@receiver(post_save, sender=ChannelUser)
def activity_handler_channel_user(sender, instance, created, **kwargs):
    if instance.channel.type == CHANNEL_TYPE_DIRECT:
        clean_direct_channel(instance.channel)


@receiver(post_save, sender=Message)
def activity_handler_new_message(sender, instance, created, **kwargs):
    if created:
        send_new_message_email.delay(instance.id)
