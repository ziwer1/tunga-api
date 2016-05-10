from django.db.models.query_utils import Q
from dry_rest_permissions.generics import DRYPermissionFiltersBase

from tunga_auth.models import USER_TYPE_DEVELOPER, USER_TYPE_PROJECT_OWNER


class UserFilterBackend(DRYPermissionFiltersBase):

    def filter_list_queryset(self, request, queryset, view):
        queryset = queryset.exclude(id=request.user.id)
        user_filter = request.query_params.get('filter', None)
        if user_filter == 'developers':
            queryset = queryset.filter(type=USER_TYPE_DEVELOPER)
        elif user_filter == 'project-owners':
            queryset = queryset.filter(type=USER_TYPE_PROJECT_OWNER)
        elif user_filter in ['team', 'my-project-owners']:
            if user_filter == 'my-project-owners':
                user_type = USER_TYPE_PROJECT_OWNER
            else:
                user_type = USER_TYPE_DEVELOPER
            queryset = queryset.filter(type=user_type).filter(
                (
                    Q(connections_initiated__to_user=request.user) &
                    Q(connections_initiated__accepted=True)
                ) |
                (
                    Q(connection_requests__from_user=request.user) &
                    Q(connection_requests__accepted=True)
                )
            )
        elif user_filter == 'requests':
            queryset = queryset.filter(
                connections_initiated__to_user=request.user, connections_initiated__responded=False)
        elif user_filter == 'relevant':
            queryset = queryset.filter(type=USER_TYPE_DEVELOPER)
            try:
                queryset = queryset.filter(userprofile__skills__in=request.user.userprofile.skills.all())
            except:
                pass
        return queryset
