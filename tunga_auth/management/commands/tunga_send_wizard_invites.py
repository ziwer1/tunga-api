import datetime

from django.core.management.base import BaseCommand

from tunga.settings import TUNGA_URL
from tunga_auth.forms import TungaPasswordResetForm
from tunga_auth.models import TungaUser
from tunga_utils.constants import USER_TYPE_PROJECT_OWNER, USER_SOURCE_TASK_WIZARD


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Send password create invites to clients that joined via the wizard.
        """
        # command to run: python manage.py tunga_send_wizard_invites

        clients = TungaUser.objects.filter(
            type=USER_TYPE_PROJECT_OWNER, source=USER_SOURCE_TASK_WIZARD,
            last_set_password_email_at__isnull=True,
            emailaddress__verified=False
        )
        for client in clients:
            form = TungaPasswordResetForm(data=dict(email=client.email))
            if form.is_valid():
                form.save(
                    subject_template_name='tunga/email/password_set_subject.txt',
                    email_template_name='tunga/email/password_set.html',
                    html_email_template_name='tunga/email/password_set.html',
                    extra_email_context=dict(tunga_url=TUNGA_URL)
                )
                client.last_set_password_email_at = datetime.datetime.utcnow()
                client.save()
