from django.db.models.aggregates import Count
from django.db.models.expressions import Case, When, F
from django.db.models.fields import IntegerField
from django.db.models.query_utils import Q
from dry_rest_permissions.generics import DRYPermissionFiltersBase


def received_messages_q_filter(user):
    return (
        ~Q(user=user) & Q(channel__channeluser__user=user)
    )


def all_messages_q_filter(user):
    return Q(user=user) | Q(channel__channeluser__user=user)


def channel_last_read_annotation(user):
    return Case(
        When(
            channel__channeluser__user=user,
            then='channel__channeluser__last_read'
        ),
        default=0,
        output_field=IntegerField()
    )


def new_messages_filter(queryset, user):
    return queryset.filter(
        received_messages_q_filter(user)
    ).annotate(
        channel_last_read=channel_last_read_annotation(user)
    ).filter(
        Q(channel_last_read=None) | Q(id__gt=F('channel_last_read'))
    )


class ChannelFilterBackend(DRYPermissionFiltersBase):

    def filter_list_queryset(self, request, queryset, view):
        return queryset.filter(channeluser__user=request.user)


class MessageFilterBackend(DRYPermissionFiltersBase):

    def filter_list_queryset(self, request, queryset, view):
        return queryset.filter(all_messages_q_filter(request.user))
