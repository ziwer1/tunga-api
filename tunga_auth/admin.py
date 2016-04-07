from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import ugettext_lazy as _

from tunga_auth.forms import TungaUserChangeForm
from tunga_auth.models import TungaUser
from tunga_profiles.admin import UserProfileInline


@admin.register(TungaUser)
class TungaUserAdmin(UserAdmin):
    form = TungaUserChangeForm
    inlines = (UserProfileInline,)

    fieldsets = UserAdmin.fieldsets + (
        (_('Profile'), {'fields': ('type', 'image')}),
    )

    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'type')
    list_filter = ('type', 'is_staff', 'is_superuser', 'is_active')
