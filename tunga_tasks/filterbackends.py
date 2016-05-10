from django.db.models.query_utils import Q
from dry_rest_permissions.generics import DRYPermissionFiltersBase

from tunga_auth.models import USER_TYPE_DEVELOPER, USER_TYPE_PROJECT_OWNER
from tunga_settings.models import VISIBILITY_DEVELOPER, VISIBILITY_MY_TEAM, VISIBILITY_CUSTOM


class TaskFilterBackend(DRYPermissionFiltersBase):

    #@dont_filter_staff_or_superuser
    def filter_list_queryset(self, request, queryset, view):
        label_filter = request.query_params.get('filter', None)
        if label_filter == 'running':
            queryset = queryset.filter(
                Q(user=request.user) |
                (
                    (Q(participation__accepted=True) | Q(participation__responded=False)) &
                    Q(participation__user=request.user))
            )
        elif label_filter == 'saved':
            queryset = queryset.filter(savedtask__user=request.user)
        elif label_filter == 'skills':
            try:
                queryset = queryset.filter(skills__in=request.user.userprofile.skills.all())
            except:
                pass
        elif label_filter == 'project-owners':
            queryset = queryset.filter(
                (
                    Q(user__connections_initiated__to_user=request.user) &
                    Q(user__connections_initiated__accepted=True)
                ) |
                (
                    Q(user__connection_requests__from_user=request.user) &
                    Q(user__connection_requests__accepted=True)
                )
            )

        if request.user.is_staff or request.user.is_superuser:
            return queryset
        if request.user.type == USER_TYPE_PROJECT_OWNER:
            queryset = queryset.filter(user=request.user)
        elif request.user.type == USER_TYPE_DEVELOPER:
            return queryset.filter(
                Q(user=request.user) |
                Q(participation__user=request.user) |
                (
                    Q(visibility=VISIBILITY_DEVELOPER) |
                    (
                        Q(visibility=VISIBILITY_CUSTOM) & Q(visible_to=request.user)
                    ) |
                    (
                        Q(visibility=VISIBILITY_MY_TEAM) &
                        (
                            (
                                Q(user__connections_initiated__to_user=request.user) &
                                Q(user__connections_initiated__accepted=True)
                            ) |
                            (
                                Q(user__connection_requests__from_user=request.user) &
                                Q(user__connection_requests__accepted=True)
                            )
                        )
                    )
                )
            ).distinct()
        else:
            return queryset.none()
        return queryset
