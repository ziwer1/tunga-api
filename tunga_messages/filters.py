import django_filters

from tunga_messages.models import Message, Reply
from tunga_utils.filters import GenericDateFilterSet


class MessageFilter(GenericDateFilterSet):

    class Meta:
        model = Message
        fields = ('user', 'is_broadcast')


class ReplyFilter(GenericDateFilterSet):

    class Meta:
        model = Reply
        fields = ('user', 'message', 'is_broadcast')


