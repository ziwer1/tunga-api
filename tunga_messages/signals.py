from actstream.signals import action
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver

from tunga_activity import verbs
from tunga_messages.models import Message, Channel, ChannelUser
from tunga_messages.notifications import notify_new_message_slack, notify_new_message_developers
from tunga_profiles.models import Inquirer
from tunga_utils.constants import CHANNEL_TYPE_DIRECT, CHANNEL_TYPE_SUPPORT, APP_INTEGRATION_PROVIDER_SLACK, \
    CHANNEL_TYPE_DEVELOPER
from tunga_messages.tasks import clean_direct_channel


@receiver(post_save, sender=Channel)
def activity_handler_channel(sender, instance, created, **kwargs):
    if created:
        actor = None
        if instance.created_by:
            actor = instance.created_by
        elif instance.content_object:
            actor = instance.content_object
        if actor:
            action.send(
                actor, verb=verbs.CREATE, action_object=instance, timestamp=instance.created_at
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
        actor = None
        if instance.user:
            actor = instance.user
        elif instance.source == APP_INTEGRATION_PROVIDER_SLACK:
            actor = instance.channel
        elif instance.channel.content_object and ContentType.objects.get_for_model(Inquirer) == ContentType.objects.get_for_model(instance.channel.content_object):
            actor = instance.channel.content_object
        elif instance.channel.type == CHANNEL_TYPE_SUPPORT:
            actor = instance.channel

        if actor:
            action.send(
                actor, verb=verbs.SEND, action_object=instance, target=instance.channel,
                timestamp=instance.created_at
            )

        if instance.channel.type == CHANNEL_TYPE_SUPPORT:
            notify_new_message_slack.delay(instance.id)

        if instance.channel.type == CHANNEL_TYPE_DEVELOPER and (instance.user.is_staff or instance.user.is_superuser):
            notify_new_message_developers.delay(instance.id)
