from django.db.models.query_utils import Q
from dry_rest_permissions.generics import DRYPermissionFiltersBase

from tunga_utils.filterbackends import dont_filter_staff_or_superuser


class ConnectionFilterBackend(DRYPermissionFiltersBase):

    @dont_filter_staff_or_superuser
    def filter_list_queryset(self, request, queryset, view):
        return queryset.filter(Q(from_user=request.user) | Q(to__user=request.user))
