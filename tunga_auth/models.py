from __future__ import unicode_literals

from django.contrib.auth.models import AbstractUser
from django.db import models

USER_TYPE_DEVELOPER = 1
USER_TYPE_PROJECT_OWNER = 2

USER_TYPE_CHOICES = (
    (USER_TYPE_DEVELOPER, 'Developer'),
    (USER_TYPE_PROJECT_OWNER, 'Project Owner')
)


class TungaUser(AbstractUser):
    type = models.IntegerField(choices=USER_TYPE_CHOICES, blank=True, null=True)
    image = models.ImageField(upload_to='photos/%Y/%m/%d', blank=True, null=True)
    last_activity = models.DateTimeField(blank=True, null=True)
    verified = models.BooleanField(default=False)
    pending = models.BooleanField(default=True)

    class Meta(AbstractUser.Meta):
        unique_together = ('email',)

    def save(self, *args, **kwargs):
        if self.type == USER_TYPE_PROJECT_OWNER:
            self.pending = False
        super(TungaUser, self).save(*args, **kwargs)

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    @property
    def display_type(self):
        return self.get_type_display()

    @property
    def is_developer(self):
        return self.type == USER_TYPE_DEVELOPER

    @property
    def is_project_owner(self):
        return self.type == USER_TYPE_PROJECT_OWNER
