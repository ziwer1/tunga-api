from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from tunga_auth.models import USER_TYPE_CHOICES


class TungaUserCreationForm(UserCreationForm):

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ('username', 'first_name', 'last_name', 'email', 'type', 'is_staff', 'is_superuser')


class TungaUserChangeForm(UserChangeForm):

    class Meta(UserChangeForm.Meta):
        model = get_user_model()


class SignupForm(forms.Form):
    type = forms.ChoiceField(choices=USER_TYPE_CHOICES, required=False)

    def signup(self, request, user):
        user.type = self.cleaned_data['type']
        user.save()
