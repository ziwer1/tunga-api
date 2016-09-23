from actstream.signals import action
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver

from tunga_activity import verbs
from tunga_messages.models import Message, Channel, ChannelUser
from tunga_utils.constants import CHANNEL_TYPE_DIRECT
from tunga_messages.tasks import clean_direct_channel


@receiver(post_save, sender=Channel)
def activity_handler_channel(sender, instance, created, **kwargs):
    if created:
        action.send(
            instance.created_by, verb=verbs.CREATE, action_object=instance, timestamp=instance.created_at
        )

    if instance.type == CHANNEL_TYPE_DIRECT:
        clean_direct_channel(instance)


@receiver(post_save, sender=ChannelUser)
def activity_handler_channel_user(sender, instance, created, **kwargs):
    if created:
        action.send(
            instance.user, verb=verbs.ADD, action_object=instance, target=instance.channel,
            timestamp=instance.created_at
        )

    if instance.channel.type == CHANNEL_TYPE_DIRECT:
        clean_direct_channel(instance.channel)


@receiver(post_save, sender=Message)
def activity_handler_new_message(sender, instance, created, **kwargs):
    if created:
        action.send(
            instance.user, verb=verbs.SEND, action_object=instance, target=instance.channel,
            timestamp=instance.created_at
        )
