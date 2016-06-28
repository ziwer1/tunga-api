from __future__ import unicode_literals

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.translation import ugettext_lazy as _
from dry_rest_permissions.generics import allow_staff_or_superuser

from tunga import settings
from tunga_auth.models import USER_TYPE_DEVELOPER
from tunga_utils.validators import validate_year

MONTHS = (
    (1, 'Jan'),
    (2, 'Feb'),
    (3, 'Mar'),
    (4, 'Apr'),
    (5, 'May'),
    (6, 'Jun'),
    (7, 'Jul'),
    (8, 'Aug'),
    (9, 'Sep'),
    (10, 'Oct'),
    (11, 'Nov'),
    (12, 'Dec')
)


class AbstractExperience(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    start_month = models.PositiveSmallIntegerField(choices=MONTHS)
    start_year = models.PositiveIntegerField(validators=[validate_year])
    end_month = models.PositiveSmallIntegerField(choices=MONTHS, blank=True, null=True)
    end_year = models.PositiveIntegerField(blank=True, null=True, validators=[validate_year])
    details = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return '%s' % self.user.get_short_name

    class Meta:
        abstract = True

    @staticmethod
    @allow_staff_or_superuser
    def has_read_permission(request):
        return True

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return True

    @staticmethod
    @allow_staff_or_superuser
    def has_write_permission(request):
        return request.user.type == USER_TYPE_DEVELOPER

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.user


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


RATING_CRITERIA_CODING = 1
RATING_CRITERIA_COMMUNICATION = 2
RATING_CRITERIA_SPEED = 3

RATING_CRITERIA_CHOICES = (
    (RATING_CRITERIA_CODING, 'Coding skills'),
    (RATING_CRITERIA_COMMUNICATION, 'Communication skills'),
    (RATING_CRITERIA_SPEED, 'Speed'),
)


class Rating(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, verbose_name=_('content type'))
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    score = models.SmallIntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)])
    criteria = models.PositiveSmallIntegerField(
        choices=RATING_CRITERIA_CHOICES, blank=True, null=True,
        help_text=','.join(['%s - %s' % (item[0], item[1]) for item in RATING_CRITERIA_CHOICES])
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='ratings_created', on_delete=models.DO_NOTHING)
    created_at = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        criteria = self.get_criteria_display()
        return '{0}{1} - {:0,.0f}%'.format(
            self.content_object, (criteria and ' - {0}'.format(criteria) or ''), self.score
        )

    class Meta:
        unique_together = ('content_type', 'object_id', 'criteria', 'created_by')
