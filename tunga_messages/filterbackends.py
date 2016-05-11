from django.db.models.aggregates import Count
from django.db.models.query_utils import Q
from dry_rest_permissions.generics import DRYPermissionFiltersBase


def received_messages_q_filter(user):
    return (
        Q(recipients=user) |
        (
            Q(is_broadcast=True) &
            (
                (
                    Q(user__connections_initiated__accepted=True) &
                    Q(user__connections_initiated__to_user=user)
                ) |
                (
                    Q(user__connection_requests__from_user=user) &
                    Q(user__connection_requests__accepted=True)
                )
            )
        )
    )


def all_messages_q_filter(user):
    return Q(user=user) | received_messages_q_filter(user)


def received_replies_q_filter(user):
    return (
        Q(message__user=user) |
        (
            Q(is_broadcast=True) &
            (
                Q(message__recipients=user) |
                (
                    Q(message__is_broadcast=True) &
                    (
                        (
                            Q(message__user__connections_initiated__accepted=True) &
                            Q(message__user__connections_initiated__to_user=user)
                        ) |
                        (
                            Q(message__user__connection_requests__from_user=user) &
                            Q(message__user__connection_requests__accepted=True)
                        )
                    )
                )
            )
        )
    )


def all_replies_q_filter(user):
    return Q(user=user) | received_replies_q_filter(user)


class MessageFilterBackend(DRYPermissionFiltersBase):

    def filter_list_queryset(self, request, queryset, view):
        label_filter = request.query_params.get('filter', None)
        if label_filter == 'sent':
            return queryset.filter(user=request.user)
        elif label_filter == 'inbox':
            return queryset.filter(
                all_messages_q_filter(request.user)
            ).annotate(reply_count=Count('replies')).exclude(user=request.user, reply_count=0)
        return queryset.filter(all_messages_q_filter(request.user))


class ReplyFilterBackend(DRYPermissionFiltersBase):

    def filter_list_queryset(self, request, queryset, view):
        return queryset.filter(all_replies_q_filter(request.user)).distinct()
