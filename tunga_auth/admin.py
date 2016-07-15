import csv

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.http.response import StreamingHttpResponse
from django.utils.translation import ugettext_lazy as _

from tunga_auth.forms import TungaUserChangeForm, TungaUserCreationForm
from tunga_profiles.admin import UserProfileInline
from tunga_utils.views import Echo


@admin.register(get_user_model())
class TungaUserAdmin(UserAdmin):
    form = TungaUserChangeForm
    add_form = TungaUserCreationForm
    actions = UserAdmin.actions + ['make_pending', 'make_not_pending', 'download_csv']

    fieldsets = UserAdmin.fieldsets + (
        (_('Profile'), {'fields': ('type', 'image')}),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        (_('Account Type'), {'fields': ('is_superuser', 'is_staff', 'type')}),
        (_('Profile'), {'fields': ('email', 'first_name', 'last_name')})
    )

    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'type', 'pending', 'verified')
    list_filter = ('type', 'pending', 'is_staff', 'is_superuser')

    inlines = (UserProfileInline,)

    def make_pending(self, request, queryset):
        rows_updated = queryset.update(pending=True)
        self.message_user(
            request, "%s user%s successfully marked as pending." % (rows_updated, (rows_updated > 1 and 's' or '')))
    make_pending.short_description = "Mark selected users as pending"

    def make_not_pending(self, request, queryset):
        rows_updated = queryset.update(pending=False)
        self.message_user(
            request, "%s user%s successfully marked as active." % (rows_updated, (rows_updated > 1 and 's' or '')))
    make_not_pending.short_description = "Mark selected users as active"

    def download_csv(self, request, queryset):
        pseudo_buffer = Echo()
        writer = csv.writer(pseudo_buffer)

        report_rows = [["Name", "E-mail", "User Type"]]
        for user in queryset:
            report_rows.append([
                user.display_name and user.display_name.encode('utf-8') or '', user.email, user.display_type]
            )

        response = StreamingHttpResponse((writer.writerow(row) for row in report_rows), content_type="text/csv")
        response['Content-Disposition'] = 'attachment; filename=tunga_users.csv'
        return response
    download_csv.short_description = "Download CSV of selected users"
