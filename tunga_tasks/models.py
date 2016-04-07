from __future__ import unicode_literals

import tagulous.models
from django.db import models

from tunga_profiles.models import Skill
from tunga import settings
from tunga_auth.models import TungaUser

CURRENCIES = (
    ('EUR', 'EUR'),
    ('USD', 'USD')
)

VISIBILITY_CHOICES = (
    (1, 'Developers'),
    (2, 'My Team'),
    (3, 'Custom'),
    (4, 'Only Me')
)

TASK_REQUEST_CHOICES = (
    (1, 'Close Request'),
    (2, 'Payment Request')
)


class Task(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='tasks_created', on_delete=models.DO_NOTHING)
    title = models.CharField(max_length=200)
    description = models.CharField(max_length=1000, blank=True, null=True)
    url = models.URLField(blank=True, null=True)
    fee = models.BigIntegerField()
    currency = models.CharField(max_length=5, choices=CURRENCIES, default=CURRENCIES[0][0])
    deadline = models.DateTimeField(blank=True, null=True)
    skills = tagulous.models.TagField(Skill)
    visibility = models.PositiveSmallIntegerField(choices=VISIBILITY_CHOICES, default=VISIBILITY_CHOICES[0][0])
    closed = models.BooleanField(default=False)
    visible_to = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='task_invites', blank=True)
    applicants = models.ManyToManyField(
            settings.AUTH_USER_MODEL, through='Application', through_fields=('task', 'user'),
            related_name='task_applications', blank=True)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='tasks_assigned', blank=True, null=True)
    participants = models.ManyToManyField(
            settings.AUTH_USER_MODEL, through='Participation', through_fields=('task', 'user'),
            related_name='task_participants', blank=True)
    satisfaction = models.SmallIntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return self.summary

    @property
    def summary(self):
        return '%s - Fee: %s %s' % (self.title, self.get_currency_display(), self.fee)

    @property
    def skills_list(self):
        return str(self.skills)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('user', 'title', 'fee')


class Application(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    accepted = models.BooleanField(default=False)
    responded = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return '%s - %s' % (self.user.get_short_name() or self.user.username, self.task.title)

    class Meta:
        unique_together = ('user', 'task')


class Participation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    accepted = models.BooleanField(default=False)
    responded = models.BooleanField(default=False)
    share = models.IntegerField(blank=True, null=True)
    satisfaction = models.SmallIntegerField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='participants_added')
    created_at = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return '%s - %s' % (self.user.get_short_name() or self.user.username, self.task.title)

    class Meta:
        unique_together = ('user', 'task')
        verbose_name_plural = 'participation'


class TaskRequest(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    type = models.PositiveSmallIntegerField(choices=TASK_REQUEST_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return '%s - %s' % (self.get_type_display(), self.task.title)


class SavedTask(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return '%s - %s' % (self.user.get_short_name() or self.user.username, self.task.title)
