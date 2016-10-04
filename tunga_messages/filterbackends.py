from django.db.models.expressions import Case, When, F
from django.db.models.fields import IntegerField
from django.db.models.query_utils import Q
from dry_rest_permissions.generics import DRYPermissionFiltersBase

from tunga_activity import verbs
from tunga_utils.constants import CHANNEL_TYPE_SUPPORT


def received_messages_q_filter(user):
    return (
        ~Q(actor_object_id=user.id)
    )


def all_messages_q_filter(user):
    return Q(user=user) | Q(channel__channeluser__user=user)


def channel_last_read_annotation(user):
    return Case(
        When(
            channels__channeluser__user=user,
            then='channels__channeluser__last_read'
        ),
        default=0,
        output_field=IntegerField()
    )


def new_messages_filter(queryset, user):
    return queryset.filter(
        ~Q(actor_object_id=user.id) &
        Q(verb__in=[verbs.SEND, verbs.UPLOAD])
    ).annotate(
        channel_last_read=channel_last_read_annotation(user)
    ).filter(
        id__gt=F('channel_last_read')
    )


class ChannelFilterBackend(DRYPermissionFiltersBase):

    def filter_list_queryset(self, request, queryset, view):
        if request.user.is_authenticated():
            queryset = queryset.filter(channeluser__user=request.user)
            if (request.user.is_staff or request.user.is_superuser) and not request.query_params.get('type', None):
                queryset = queryset.exclude(type=CHANNEL_TYPE_SUPPORT)
            return queryset
        return queryset.none()


class MessageFilterBackend(DRYPermissionFiltersBase):

    def filter_list_queryset(self, request, queryset, view):
        if request.user.is_authenticated():
            return queryset.filter(all_messages_q_filter(request.user)).distinct()
        return queryset.none()
