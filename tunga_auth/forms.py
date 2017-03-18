from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserChangeForm, UserCreationForm, PasswordResetForm
from django.template import loader

from tunga_auth.models import USER_TYPE_CHOICES
from tunga_utils.emails import send_mail


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


class TungaPasswordResetForm(PasswordResetForm):

    def send_mail(self, subject_template_name, email_template_name,
                  context, from_email, to_email, html_email_template_name=None):
        subject = loader.render_to_string(subject_template_name, context)
        # Email subject *must not* contain newlines
        subject = ''.join(subject.splitlines())
        template_prefix = (html_email_template_name or email_template_name).replace('.txt', '').replace('.html', '')
        send_mail(subject, template_prefix=template_prefix, to_emails=[to_email], context=context)
