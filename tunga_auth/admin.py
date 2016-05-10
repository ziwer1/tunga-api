from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import ugettext_lazy as _

from tunga_auth.forms import TungaUserChangeForm, TungaUserCreationForm


@admin.register(get_user_model())
class TungaUserAdmin(UserAdmin):
    form = TungaUserChangeForm
    add_form = TungaUserCreationForm

    fieldsets = UserAdmin.fieldsets + (
        (_('Profile'), {'fields': ('type', 'image')}),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        (_('Account Type'), {'fields': ('is_superuser', 'is_staff', 'type')}),
        (_('Profile'), {'fields': ('email', 'first_name', 'last_name')})
    )

    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'type', 'verified')
    list_filter = ('type', 'is_staff', 'is_superuser', 'is_active')
