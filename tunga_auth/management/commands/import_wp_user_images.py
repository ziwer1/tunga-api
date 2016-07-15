import os

from django.contrib.auth import get_user_model
from django.core.files.base import File
from django.core.management.base import BaseCommand

from tunga.settings import MEDIA_ROOT


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Creates all auth emails for all wordpress users.
        """
        # command to run: python manage.py import_wp_user_images

        users = get_user_model().objects.exclude(image__startswith='photos')
        for user in users:
            user_dir = MEDIA_ROOT + '/wp_avatars/%s/' % user.id
            if os.path.isdir(user_dir):
                images = os.listdir(user_dir)
                if images:
                    user.image.save(images[0], File(open('%s%s' % (user_dir, images[0]))))
                    user.save()
                    print user.pk
                    print user.image

        print "%s users inspected" % len(users)
