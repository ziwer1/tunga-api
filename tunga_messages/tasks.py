from tunga_messages.models import Channel, ChannelUser, Message, CHANNEL_TYPE_TOPIC, CHANNEL_TYPE_DIRECT
from tunga_utils.decorators import catch_all_exceptions

@catch_all_exceptions
def create_channel(
        initiator, participants, subject=None, messages=None, content_object=None,
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


def clean_direct_channel(channel):
    # A direct channel can't have more than 2 participants
    if channel.type == CHANNEL_TYPE_DIRECT and channel.participants.count() > 2:
        channel.type = CHANNEL_TYPE_TOPIC
        channel.save()
