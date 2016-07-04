from rest_framework import permissions
from rest_framework.permissions import IsAdminUser


class IsAdminOrCreateOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method == 'POST':
            return True
        return IsAdminUser().has_permission(request, view)
