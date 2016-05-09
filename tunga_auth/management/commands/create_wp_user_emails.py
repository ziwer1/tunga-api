from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Creates all auth emails for all wordpress users.
        """
        # command to run: python manage.py create_wp_user_emails

        users = get_user_model().objects.filter(password__startswith='phpass$$P$B')
        for user in users:
            email_address = EmailAddress.objects.add_email(None, user, user.email)
            email_address.verified = True
            email_address.primary = True
            email_address.save()
            print user.pk

        print "%s emails created" % len(users)
