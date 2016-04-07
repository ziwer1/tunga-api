from django.contrib import admin

from tunga_profiles.models import UserProfile, SocialPlatform, SocialLink, Education, Work, Connection
from tunga_utils.admin import AdminAutoCreatedBy


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name = 'user profile'


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
