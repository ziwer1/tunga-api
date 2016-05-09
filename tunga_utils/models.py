from __future__ import unicode_literals

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import ugettext_lazy as _
from dry_rest_permissions.generics import allow_staff_or_superuser

from tunga import settings


class GenericUpload(models.Model):
    file = models.FileField(verbose_name='Upload', upload_to='uploads/%Y/%m/%d')
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, verbose_name=_('content type'))
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    created_at = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return self.file.name

    class Meta:
        ordering = ['-created_at']
        abstract = True


class Upload(GenericUpload):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.user


class ContactRequest(models.Model):
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return '%s on %s' % (self.email, self.created_at)
