import django_filters

from tunga_messages.models import Message, Channel
from tunga_utils.filters import GenericDateFilterSet


class ChannelFilter(GenericDateFilterSet):
    user = django_filters.NumberFilter(name='channeluser__user')

    class Meta:
        model = Channel
        fields = ('user',)


class MessageFilter(GenericDateFilterSet):
    since = django_filters.NumberFilter(name='id', lookup_type='gt')

    class Meta:
        model = Message
        fields = ('user', 'channel', 'since')

