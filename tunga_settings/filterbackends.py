from dry_rest_permissions.generics import DRYPermissionFiltersBase


class UserSettingFilterBackend(DRYPermissionFiltersBase):

    def filter_list_queryset(self, request, queryset, view):
        return queryset.filter(user=request.user)

