from __future__ import unicode_literals

from actstream.models import Action
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models.query_utils import Q
from django.utils.html import strip_tags
from django.utils.translation import ugettext_lazy as _
from dry_rest_permissions.generics import allow_staff_or_superuser

from tunga import settings
from tunga_profiles.models import Connection
from tunga_utils.constants import CHANNEL_TYPE_DIRECT, CHANNEL_TYPE_TOPIC
from tunga_utils.models import Upload


class Attachment(models.Model):
    file = models.FileField(verbose_name='Attachment', upload_to='attachments/%Y/%m/%d')
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, verbose_name=_('content type'))
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    created_at = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return self.file.name

    class Meta:
        ordering = ['-created_at']


CHANNEL_TYPE_CHOICES = (
    (CHANNEL_TYPE_DIRECT, 'Direct Channel'),
    (CHANNEL_TYPE_TOPIC, 'Topic Channel')
)


class Channel(models.Model):
    subject = models.CharField(max_length=100, blank=True, null=True)
    participants = models.ManyToManyField(
            settings.AUTH_USER_MODEL, through='ChannelUser', through_fields=('channel', 'user'),
            related_name='channels', blank=True)
    type = models.PositiveSmallIntegerField(
        choices=CHANNEL_TYPE_CHOICES, default=CHANNEL_TYPE_TOPIC,
        help_text=','.join(['%s - %s' % (item[0], item[1]) for item in CHANNEL_TYPE_CHOICES])
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='channels_created', on_delete=models.DO_NOTHING)
    created_at = models.DateTimeField(auto_now_add=True)
    # The object of the channel, nullable for pure messages
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, verbose_name=_('content type'), blank=True, null=True
    )
    object_id = models.PositiveIntegerField(blank=True, null=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    attachments = GenericRelation(Upload, related_query_name='channels')
    action_targets = GenericRelation(
        Action,
        object_id_field='target_object_id',
        content_type_field='target_content_type',
        related_query_name='channels'
    )

    def __unicode__(self):
        return '{0} - {1}'.format(self.get_type_display(), self.subject or self.created_by)

    class Meta:
        ordering = ['-created_at']

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        if self.has_object_write_permission(request):
            return True
        return self.channeluser_set.filter(user=request.user).count()

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.created_by

    @property
    def all_attachments(self):
        return Upload.objects.filter(Q(channels=self) | Q(messages__channel=self))

    def get_receiver(self, sender):
        if sender and self.type == CHANNEL_TYPE_DIRECT:
            participation = self.channeluser_set.filter(~Q(user_id=sender.id))
            if participation:
                return participation[0].user
        return None

    def get_channel_display_name(self, sender):
        if self.type == CHANNEL_TYPE_DIRECT:
            user = self.get_receiver(sender)
            if user:
                return user.display_name
        elif self.subject:
            return self.subject
        return self


class ChannelUser(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    last_read = models.IntegerField(default=0)
    last_email_at = models.DateTimeField(blank=True, null=True)

    def __unicode__(self):
        return '%s - %s' % (self.channel, self.user.get_short_name() or self.user.username)

    class Meta:
        unique_together = ('user', 'channel')


class Message(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, blank=True, null=True, related_name='messages')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='messages')
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    attachments = GenericRelation(Upload, related_query_name='messages')
    activity_objects = GenericRelation(
        Action,
        object_id_field='action_object_object_id',
        content_type_field='action_object_content_type',
        related_query_name='messages'
    )

    def __unicode__(self):
        return '%s - %s' % (self.user.get_short_name() or self.user.username, self.body)

    class Meta:
        ordering = ['-created_at']

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        if self.has_object_write_permission(request):
            return True
        return self.channel.channeluser_set.filter(user=request.user).count()

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.user

    @property
    def excerpt(self):
        return strip_tags(self.body)
