from __future__ import unicode_literals

from django.db import models

from tunga import settings

FROM_STATUS_DRAFT = 1
FROM_STATUS_SENT = 2
FROM_STATUS_DELETED = 3

FROM_STATUS_CHOICES = (
    (FROM_STATUS_DRAFT, 'Draft'),
    (FROM_STATUS_SENT, 'Sent'),
    (FROM_STATUS_DELETED, 'Deleted')
)

TO_STATUS_NEW = 1
TO_STATUS_READ = 2
TO_STATUS_DELETED = 3

TO_STATUS_CHOICES = (
    (TO_STATUS_NEW, 'New'),
    (TO_STATUS_READ, 'Read'),
    (TO_STATUS_DELETED, 'Deleted')
)


class Message(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    is_broadcast = models.BooleanField(default=False)
    recipients = models.ManyToManyField(
            settings.AUTH_USER_MODEL, through='Recipient', through_fields=('message', 'user'),
            related_name='message_recipients', blank=True)
    subject = models.CharField(max_length=100)
    body = models.TextField()
    status = models.SmallIntegerField(choices=FROM_STATUS_CHOICES, default=FROM_STATUS_SENT)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    def __unicode__(self):
        return '%s - %s' % (self.user.get_short_name() or self.user.username, self.subject)


class Recipient(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.ForeignKey(Message, on_delete=models.CASCADE)
    status = models.SmallIntegerField(choices=TO_STATUS_CHOICES, default=TO_STATUS_NEW)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    def __unicode__(self):
        return '%s - %s' % (self.user.get_short_name() or self.user.username, self.message.subject)

    class Meta:
        unique_together = ('user', 'message')


class Reply(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='replies')
    is_broadcast = models.BooleanField(default=True)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return '%s -> %s' % (self.user.get_short_name() or self.user.username, self.body)

    class Meta:
        verbose_name_plural = 'replies'
