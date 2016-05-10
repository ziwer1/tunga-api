from django.db.models.query_utils import Q
from dry_rest_permissions.generics import DRYPermissionFiltersBase


class MessageFilterBackend(DRYPermissionFiltersBase):

    def filter_list_queryset(self, request, queryset, view):
        label_filter = request.query_params.get('filter', None)
        if label_filter == 'sent':
            return queryset.filter(user=request.user)
        elif label_filter == 'inbox':
            return queryset.filter(
                Q(recipients=request.user) |
                (
                    Q(is_broadcast=True) & (
                        (
                            Q(user__connections_initiated__accepted=True) &
                            Q(user__connections_initiated__to_user=request.user)
                        ) |
                        (
                            Q(user__connection_requests__from_user=request.user) &
                            Q(user__connection_requests__accepted=True)
                        )
                    )
                )
            )
        return queryset.filter(
            Q(user=request.user) | Q(recipients=request.user) |
            (
                Q(is_broadcast=True) &
                (
                    (
                        Q(user__connections_initiated__accepted=True) &
                        Q(user__connections_initiated__to_user=request.user)
                    ) |
                    (
                        Q(user__connection_requests__from_user=request.user) &
                        Q(user__connection_requests__accepted=True)
                    )
                )
            )
        )


class ReplyFilterBackend(DRYPermissionFiltersBase):

    def filter_list_queryset(self, request, queryset, view):
        return queryset.filter(
            Q(user=request.user) | Q(message__user=request.user) |
            (
                Q(is_broadcast=True) &
                (
                    Q(message__recipients=request.user) |
                    (
                        Q(message__is_broadcast=True) &
                        (
                            (
                                Q(message__user__connections_initiated__accepted=True) &
                                Q(message__user__connections_initiated__to_user=request.user)
                            ) |
                            (
                                Q(message__user__connection_requests__from_user=request.user) &
                                Q(message__user__connection_requests__accepted=True)
                            )
                        )
                    )
                )
            )
        ).distinct()
