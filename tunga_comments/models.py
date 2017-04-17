from __future__ import unicode_literals

import re

from actstream.models import Action
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.html import strip_tags
from django.utils.translation import ugettext_lazy as _
from dry_rest_permissions.generics import allow_staff_or_superuser

from tunga import settings
from tunga_utils.helpers import convert_to_text, convert_to_html
from tunga_utils.models import Upload


@python_2_unicode_compatible
class Comment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    body = models.TextField()
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, verbose_name=_('content type'))
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    created_at = models.DateTimeField(auto_now_add=True)
    uploads = GenericRelation(Upload, related_query_name='comments')
    activity_objects = GenericRelation(
        Action,
        object_id_field='action_object_object_id',
        content_type_field='action_object_content_type',
        related_query_name='comments'
    )

    def __str__(self):
        msg = self.body
        msg = msg and len(msg) > 100 and msg[:100] + '...' or msg
        return '%s - %s' % (self.user.get_short_name() or self.user.username, msg)

    class Meta:
        ordering = ['-created_at']

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return True

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.user

    @property
    def excerpt(self):
        return strip_tags(self.body)

    @property
    def text_body(self):
        return convert_to_text(self.body)

    @property
    def html_body(self):
        return convert_to_html(self.body)
