from django.db.models.query_utils import Q
from dry_rest_permissions.generics import DRYPermissionFiltersBase

from tunga_messages.utils import all_messages_q_filter
from tunga_utils.constants import CHANNEL_TYPE_SUPPORT, CHANNEL_TYPE_DEVELOPER


class ChannelFilterBackend(DRYPermissionFiltersBase):

    def filter_list_queryset(self, request, queryset, view):
        if request.user.is_authenticated():
            if request.user.is_staff or request.user.is_superuser:
                queryset = queryset.filter(
                    Q(channeluser__user=request.user) | Q(type=CHANNEL_TYPE_SUPPORT) | Q(type=CHANNEL_TYPE_DEVELOPER)
                )
            elif request.user.is_developer:
                queryset = queryset.filter(
                    Q(channeluser__user=request.user) | Q(type=CHANNEL_TYPE_DEVELOPER)
                )
            else:
                queryset = queryset.filter(channeluser__user=request.user)
            if not request.query_params.get('type', None):
                queryset = queryset.exclude(type=CHANNEL_TYPE_SUPPORT)
            return queryset
        return queryset.none()


class MessageFilterBackend(DRYPermissionFiltersBase):

    def filter_list_queryset(self, request, queryset, view):
        if request.user.is_authenticated():
            return queryset.filter(all_messages_q_filter(request.user)).distinct()
        return queryset.none()
