from django import forms
from django.contrib.auth.forms import UserChangeForm

from tunga_auth.models import TungaUser, USER_TYPES


class TungaUserChangeForm(UserChangeForm):

    class Meta(UserChangeForm.Meta):
        model = TungaUser


class SignupForm(forms.Form):
    type = forms.ChoiceField(choices=USER_TYPES)

    def signup(self, request, user):
        user.type = self.cleaned_data['type']
        user.save()
