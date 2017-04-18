from __future__ import unicode_literals

import re

from actstream.models import Action
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.html import strip_tags
from django.utils.translation import ugettext_lazy as _
from dry_rest_permissions.generics import allow_staff_or_superuser

from tunga import settings
from tunga_utils.constants import USER_TYPE_DEVELOPER, RATING_CRITERIA_CODING, RATING_CRITERIA_COMMUNICATION, \
    RATING_CRITERIA_SPEED, MONTHS, CONTACT_REQUEST_ITEM_ONBOARDING, CONTACT_REQUEST_ITEM_PROJECT, \
    CONTACT_REQUEST_ITEM_ONBOARDING_SPECIAL, CONTACT_REQUEST_ITEM_DO_IT_YOURSELF
from tunga_utils.validators import validate_year


@python_2_unicode_compatible
class AbstractExperience(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    start_month = models.PositiveSmallIntegerField(choices=MONTHS)
    start_year = models.PositiveIntegerField(validators=[validate_year])
    end_month = models.PositiveSmallIntegerField(choices=MONTHS, blank=True, null=True)
    end_year = models.PositiveIntegerField(blank=True, null=True, validators=[validate_year])
    details = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
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
        return request.user.is_developer

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.user


@python_2_unicode_compatible
class GenericUpload(models.Model):
    file = models.FileField(verbose_name='Upload', upload_to='uploads/%Y/%m/%d')
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, verbose_name=_('content type'))
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file.name

    class Meta:
        ordering = ['-created_at']
        abstract = True


# @python_2_unicode_compatible
class Upload(GenericUpload):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, blank=True, null=True)

    activity_objects = GenericRelation(
        Action,
        object_id_field='action_object_object_id',
        content_type_field='action_object_content_type',
        related_query_name='uploads'
    )

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.user

CONTACT_REQUEST_ITEM_CHOICES = (
    (CONTACT_REQUEST_ITEM_DO_IT_YOURSELF, 'Do-it-yourself'),
    (CONTACT_REQUEST_ITEM_ONBOARDING, 'Tunga onboarding'),
    (CONTACT_REQUEST_ITEM_ONBOARDING_SPECIAL, 'Onboarding special offer'),
    (CONTACT_REQUEST_ITEM_PROJECT, 'Tunga project'),
)


@python_2_unicode_compatible
class ContactRequest(models.Model):
    email = models.EmailField()
    item = models.CharField(
        max_length=50, choices=CONTACT_REQUEST_ITEM_CHOICES, blank=True, null=True,
        help_text=','.join(['%s - %s' % (item[0], item[1]) for item in CONTACT_REQUEST_ITEM_CHOICES])
    )
    created_at = models.DateTimeField(auto_now_add=True)
    email_sent_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return '%s on %s' % (self.email, self.created_at)


RATING_CRITERIA_CHOICES = (
    (RATING_CRITERIA_CODING, 'Coding skills'),
    (RATING_CRITERIA_COMMUNICATION, 'Communication skills'),
    (RATING_CRITERIA_SPEED, 'Speed'),
)


@python_2_unicode_compatible
class Rating(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, verbose_name=_('content type'))
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    score = models.SmallIntegerField(validators=[MinValueValidator(0), MaxValueValidator(10)])
    criteria = models.PositiveSmallIntegerField(
        choices=RATING_CRITERIA_CHOICES, blank=True, null=True,
        help_text=','.join(['%s - %s' % (item[0], item[1]) for item in RATING_CRITERIA_CHOICES])
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='ratings_created', on_delete=models.DO_NOTHING)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        criteria = self.get_criteria_display()
        return '{}{} - {:0,.0f}%'.format(
            self.content_object, (criteria and ' - {0}'.format(criteria) or ''), self.score*10
        )

    class Meta:
        unique_together = ('content_type', 'object_id', 'criteria', 'created_by')


def generate_excerpt(source):
    try:
        return strip_tags(re.sub(r'<br\s*/>', '\n', source)).strip()
    except:
        return None
