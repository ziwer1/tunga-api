from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm
from django.core.management.base import BaseCommand

from tunga.settings import TUNGA_URL
from tunga_utils.constants import USER_TYPE_PROJECT_OWNER, USER_SOURCE_TASK_WIZARD


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Send invites to clients that joined via the wizard.
        """
        # command to run: python manage.py tunga_send_wizard_invites

        clients = get_user_model().objects.filter(type=USER_TYPE_PROJECT_OWNER, source=USER_SOURCE_TASK_WIZARD)
        for client in clients:
            form = PasswordResetForm(data=dict(email=client.email))
            if form.is_valid():
                form.save(
                    subject_template_name='registration/password_set_subject.txt',
                    email_template_name='registration/password_set_email.txt',
                    html_email_template_name='registration/password_set_email.html',
                    extra_email_context=dict(tunga_url=TUNGA_URL)
                )
                print client

