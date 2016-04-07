from __future__ import unicode_literals

from django.contrib.auth.models import AbstractUser
from django.db import models

from tunga_profiles.models import Skill

USER_TYPES = (
    (1, 'Developer'),
    (2, 'Project Owner')
)


class TungaUser(AbstractUser):
    type = models.IntegerField(choices=USER_TYPES, blank=True, null=True)
    image = models.ImageField(upload_to='photos/%Y/%m/%d', blank=True, null=True)

    class Meta(AbstractUser.Meta):
        unique_together = ('email',)
