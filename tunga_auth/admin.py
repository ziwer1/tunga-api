from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import ugettext_lazy as _

from tunga_auth.forms import TungaUserChangeForm, TungaUserCreationForm


@admin.register(get_user_model())
class TungaUserAdmin(UserAdmin):
    form = TungaUserChangeForm
    add_form = TungaUserCreationForm
    actions = UserAdmin.actions + ['make_pending', 'make_not_pending']

    fieldsets = UserAdmin.fieldsets + (
        (_('Profile'), {'fields': ('type', 'image')}),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        (_('Account Type'), {'fields': ('is_superuser', 'is_staff', 'type')}),
        (_('Profile'), {'fields': ('email', 'first_name', 'last_name')})
    )

    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'type', 'pending', 'verified')
    list_filter = ('type', 'pending', 'is_staff', 'is_superuser')

    def make_pending(self, request, queryset):
        rows_updated = queryset.update(pending=True)
        self.message_user(
            request, "%s user%s successfully marked as pending." % (rows_updated, (rows_updated == 1 and '' or 's')))
    make_pending.short_description = "Mark selected users as pending"

    def make_not_pending(self, request, queryset):
        rows_updated = queryset.update(pending=False)
        self.message_user(
            request, "%s user%s successfully marked as active." % (rows_updated, (rows_updated == 1 and '' or 's')))
    make_not_pending.short_description = "Mark selected users as active"
