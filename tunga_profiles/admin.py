from django.contrib import admin

from tunga_profiles.emails import send_developer_accepted_email
from tunga_profiles.models import SocialPlatform, SocialLink, Education, Work, Connection, \
    DeveloperApplication, BTCWallet, UserProfile
from tunga_utils.admin import AdminAutoCreatedBy
from tunga_utils.constants import REQUEST_STATUS_ACCEPTED, REQUEST_STATUS_REJECTED


class UserProfileInline(admin.StackedInline):
    verbose_name = 'profile info'
    model = UserProfile


@admin.register(BTCWallet)
class BTCWalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'provider', 'token', 'token_secret', 'expires_at')
    list_filter = ('provider',)


@admin.register(SocialPlatform)
class SocialPlatformAdmin(AdminAutoCreatedBy):
    pass


@admin.register(SocialLink)
class SocialLinkAdmin(admin.ModelAdmin):
    pass


@admin.register(Education)
class EducationAdmin(admin.ModelAdmin):
    list_display = ('user', 'institution', 'award')


@admin.register(Work)
class WorkAdmin(admin.ModelAdmin):
    list_display = ('user', 'company', 'position')


@admin.register(Connection)
class ConnectionAdmin(admin.ModelAdmin):
    list_display = ('from_user', 'to_user', 'accepted', 'responded')
    list_filter = ('accepted', 'responded')


@admin.register(DeveloperApplication)
class DeveloperApplicationAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'email', 'phone_number', 'country_name', 'city', 'status')
    list_filter = ('status', 'created_at')
    readonly_fields = (
        'first_name', 'last_name',
        'email', 'phone_number', 'country', 'city',
        'stack', 'experience', 'discovery_story',
        'confirmation_sent_at', 'used', 'used_at',
    )
    actions = ['accept_users', 'reject_users']

    def has_add_permission(self, request):
        return False

    def accept_users(self, request, queryset):
        rows_updated = queryset.update(status=REQUEST_STATUS_ACCEPTED)
        self.message_user(
            request, "%s developer%s successfully marked as accepted." % (rows_updated, (rows_updated > 1 and 's' or '')))

        # Send developer accepted emails manually, queryset updates do not invoke the 'post_save' signal
        for developer in queryset:
            send_developer_accepted_email.delay(developer.id)
    accept_users.short_description = "Accept selected developers"

    def reject_users(self, request, queryset):
        rows_updated = queryset.update(status=REQUEST_STATUS_REJECTED)
        self.message_user(
            request, "%s developer%s successfully marked as rejected." % (rows_updated, (rows_updated > 1 and 's' or '')))
    reject_users.short_description = "Reject selected developers"
