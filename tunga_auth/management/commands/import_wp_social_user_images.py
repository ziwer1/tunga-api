import os
import urllib

from django.contrib.auth import get_user_model
from django.core.files.base import File
from django.core.management.base import BaseCommand


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Creates all auth emails for all wordpress users.
        """
        # command to run: python manage.py import_wp_social_user_images.py

        users = get_user_model().objects.filter(image__startswith='http')
        for user in users:
            result = urllib.urlretrieve(user.image.name)
            user.image.save(os.path.basename(user.image.name), File(open(result[0])))
            user.save()
            print user.pk
            print user.image

        print "%s users inspected" % len(users)
