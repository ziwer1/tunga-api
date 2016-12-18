from dry_rest_permissions.generics import DRYPermissionFiltersBase

from tunga_utils.constants import VISIBILITY_ALL, VISIBILITY_DEVELOPERS, VISIBILITY_PROJECT_OWNERS
from tunga_utils.filterbackends import dont_filter_staff_or_superuser


class SupportFilterBackend(DRYPermissionFiltersBase):
    @dont_filter_staff_or_superuser
    def filter_list_queryset(self, request, queryset, view):
        if request.user.is_authenticated():
            if request.user.is_developer:
                queryset = queryset.filter(visibility__in=[VISIBILITY_ALL, VISIBILITY_DEVELOPERS])
            elif request.user.is_project_owner:
                queryset = queryset.filter(visibility__in=[VISIBILITY_ALL, VISIBILITY_PROJECT_OWNERS])
        return queryset
