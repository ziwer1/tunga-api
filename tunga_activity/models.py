from __future__ import unicode_literals

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _

from tunga import settings


@python_2_unicode_compatible
class ActivityReadLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, verbose_name=_('content type'))
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    created_at = models.DateTimeField(auto_now_add=True)
    last_read = models.IntegerField(default=0)
    last_email_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return '%s - %s #%s' % (self.user.get_short_name() or self.user.username, self.content_type, self.object_id)

    class Meta:
        unique_together = ('user', 'content_type', 'object_id')
