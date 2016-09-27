from django_rq.decorators import job

from tunga_messages.models import Channel, ChannelUser, Message
from tunga_utils.constants import CHANNEL_TYPE_DIRECT, CHANNEL_TYPE_TOPIC
from tunga_utils.helpers import clean_instance


def create_channel(
        initiator, participants=None, subject=None, messages=None, content_object=None,
        channel_type=CHANNEL_TYPE_TOPIC):
    channel = Channel.objects.create(
        subject=subject, created_by=initiator, type=channel_type, content_object=content_object
    )
    all_participants = [initiator]
    if participants and isinstance(participants, list):
        all_participants.extend(participants)
    for participant in all_participants:
        ChannelUser.objects.update_or_create(channel=channel, user=participant)
    if messages:
        for message in messages:
            Message.objects.create(channel=channel, **message)
    return channel


def get_or_create_direct_channel(initiator, participant):
    try:
        return Channel.objects.filter(
            type=CHANNEL_TYPE_DIRECT, participants=initiator
        ).filter(participants=participant).earliest('created_at')
    except Channel.DoesNotExist:
        return create_channel(
            initiator=initiator, participants=[participant], channel_type=CHANNEL_TYPE_DIRECT
        )


@job
def clean_direct_channel(channel):
    channel = clean_instance(channel, Channel)
    # A direct channel can't have more than 2 participants
    if channel.type == CHANNEL_TYPE_DIRECT and channel.participants.count() > 2:
        channel.type = CHANNEL_TYPE_TOPIC
        channel.save()
