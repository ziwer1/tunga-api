# encoding=utf8
from __future__ import unicode_literals

import re
import urllib

import requests
import tagulous.models
from allauth.socialaccount import providers
from django.contrib.contenttypes.fields import GenericRelation, GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.query_utils import Q
from django.template.defaultfilters import floatformat
from django.utils.crypto import get_random_string
from django.utils.html import strip_tags
from django.utils.translation import ugettext_lazy as _
from dry_rest_permissions.generics import allow_staff_or_superuser

from tunga import settings
from tunga.settings.base import TUNGA_SHARE_PERCENTAGE, TUNGA_SHARE_EMAIL
from tunga_auth.models import USER_TYPE_DEVELOPER, USER_TYPE_PROJECT_OWNER
from tunga_comments.models import Comment
from tunga_messages.models import Channel
from tunga_profiles.models import Skill, Connection
from tunga_settings.models import VISIBILITY_DEVELOPER, VISIBILITY_MY_TEAM, VISIBILITY_CUSTOM, VISIBILITY_CHOICES
from tunga_utils.models import Upload, Rating

CURRENCY_EUR = 'EUR'
CURRENCY_USD = 'USD'

CURRENCY_CHOICES = (
    (CURRENCY_EUR, 'EUR'),
    (CURRENCY_USD, 'USD')
)

CURRENCY_SYMBOLS = {
    'EUR': '€',
    'USD': '$'
}

UPDATE_SCHEDULE_HOURLY = 1
UPDATE_SCHEDULE_DAILY = 2
UPDATE_SCHEDULE_WEEKLY = 3
UPDATE_SCHEDULE_MONTHLY = 4
UPDATE_SCHEDULE_QUATERLY = 5
UPDATE_SCHEDULE_ANNUALLY = 6

UPDATE_SCHEDULE_CHOICES = (
    (UPDATE_SCHEDULE_HOURLY, 'Hour'),
    (UPDATE_SCHEDULE_DAILY, 'Day'),
    (UPDATE_SCHEDULE_WEEKLY, 'Week'),
    (UPDATE_SCHEDULE_MONTHLY, 'Month'),
    (UPDATE_SCHEDULE_QUATERLY, 'Quarter'),
    (UPDATE_SCHEDULE_ANNUALLY, 'Annual')
)


class Project(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='projects_created', on_delete=models.DO_NOTHING)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    deadline = models.DateTimeField(blank=True, null=True)
    closed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(blank=True, null=True)

    def __unicode__(self):
        return self.title

    class Meta:
        ordering = ['-created_at']
        unique_together = ('user', 'title')

    @staticmethod
    @allow_staff_or_superuser
    def has_read_permission(request):
        return request.user.type == USER_TYPE_PROJECT_OWNER

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return request.user == self.user

    @staticmethod
    @allow_staff_or_superuser
    def has_write_permission(request):
        return request.user.type == USER_TYPE_PROJECT_OWNER

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.user

    @property
    def excerpt(self):
        try:
            return strip_tags(self.description).strip()
        except:
            return None


class Task(models.Model):
    project = models.ForeignKey(Project, related_name='tasks', on_delete=models.DO_NOTHING, blank=True, null=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='tasks_created', on_delete=models.DO_NOTHING)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    url = models.URLField(blank=True, null=True)
    fee = models.BigIntegerField()
    currency = models.CharField(max_length=5, choices=CURRENCY_CHOICES, default=CURRENCY_CHOICES[0][0])
    deadline = models.DateTimeField(blank=True, null=True)
    skills = tagulous.models.TagField(Skill, blank=True)
    visibility = models.PositiveSmallIntegerField(choices=VISIBILITY_CHOICES, default=VISIBILITY_CHOICES[0][0])
    update_interval = models.PositiveIntegerField(blank=True, null=True)
    update_interval_units = models.PositiveSmallIntegerField(choices=UPDATE_SCHEDULE_CHOICES, blank=True, null=True)
    apply = models.BooleanField(default=True)
    closed = models.BooleanField(default=False)
    paid = models.BooleanField(default=False)
    applicants = models.ManyToManyField(
            settings.AUTH_USER_MODEL, through='Application', through_fields=('task', 'user'),
            related_name='task_applications', blank=True)
    participants = models.ManyToManyField(
            settings.AUTH_USER_MODEL, through='Participation', through_fields=('task', 'user'),
            related_name='task_participants', blank=True)
    satisfaction = models.SmallIntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    apply_closed_at = models.DateTimeField(blank=True, null=True)
    closed_at = models.DateTimeField(blank=True, null=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    comments = GenericRelation(Comment, related_query_name='tasks')
    uploads = GenericRelation(Upload, related_query_name='tasks')
    ratings = GenericRelation(Rating, related_query_name='tasks')

    def __unicode__(self):
        return self.summary

    class Meta:
        ordering = ['-created_at']
        unique_together = ('user', 'title', 'fee')

    @staticmethod
    @allow_staff_or_superuser
    def has_read_permission(request):
        return True

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        if self.visibility == VISIBILITY_DEVELOPER:
            return request.user.type == USER_TYPE_DEVELOPER
        elif self.visibility == VISIBILITY_MY_TEAM:
            return bool(
                Connection.objects.exclude(accepted=False).filter(
                    Q(from_user=self.user, to_user=request.user) | Q(from_user=request.user, to_user=self.user)
                ).count()
            )
        elif self.visibility == VISIBILITY_CUSTOM:
            return self.participation_set.filter((Q(accepted=True) | Q(responded=False)), user=request.user).count()
        return False

    @staticmethod
    @allow_staff_or_superuser
    def has_write_permission(request):
        return request.user.type == USER_TYPE_PROJECT_OWNER

    @staticmethod
    @allow_staff_or_superuser
    def has_update_permission(request):
        return True

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.user

    @allow_staff_or_superuser
    def has_object_update_permission(self, request):
        if self.has_object_write_permission(request):
            return True
        # Participants can edit participation info directly on task object
        if request.method in ['PUT', 'PATCH']:
            allowed_keys = ['assignee', 'participants', 'confirmed_participants', 'rejected_participants']
            if not [x for x in request.data.keys() if not x in allowed_keys]:
                return self.participation_set.filter((Q(accepted=True) | Q(responded=False)), user=request.user).count()
        return False

    def display_fee(self, amount=None):
        if amount is None:
            amount = self.fee
        if self.currency in CURRENCY_SYMBOLS:
            return '%s%s' % (CURRENCY_SYMBOLS[self.currency], floatformat(amount, arg=-2))
        return amount

    @property
    def summary(self):
        return '%s - Fee: %s' % (self.title, self.display_fee())

    @property
    def excerpt(self):
        try:
            return strip_tags(self.description).strip()
        except:
            return None

    @property
    def skills_list(self):
        return str(self.skills)

    @property
    def milestones(self):
        return self.progressevent_set.filter(type__in=[PROGRESS_EVENT_TYPE_MILESTONE, PROGRESS_EVENT_TYPE_SUBMIT])

    @property
    def progress_events(self):
        return self.progressevent_set.all()

    @property
    def participation(self):
        return self.participation_set.filter(Q(accepted=True) | Q(responded=False))

    @property
    def assignee(self):
        try:
            return self.participation_set.get((Q(accepted=True) | Q(responded=False)), assignee=True)
        except:
            return None

    @property
    def update_schedule_display(self):
        if self.update_interval and self.update_interval_units:
            if self.update_interval == 1 and self.update_interval_units == UPDATE_SCHEDULE_DAILY:
                return 'Daily'
            interval_units = str(self.get_update_interval_units_display()).lower()
            if self.update_interval == 1:
                return 'Every %s' % interval_units
            return 'Every %s %ss' % (self.update_interval, interval_units)
        return None

    @property
    def applications(self):
        return self.application_set.filter(responded=False)

    @property
    def all_uploads(self):
        return Upload.objects.filter(Q(tasks=self) | Q(comments__tasks=self) | Q(progress_reports__event__task=self))

    @property
    def meta_payment(self):
        return {'task_url': '/task/%s/' % self.id, 'amount': self.fee, 'currency': self.currency}

    def get_default_participation(self):
        tags = ['tunga.io', 'tunga']
        if self.skills:
            tags.extend(str(self.skills).split(','))
        tunga_share = '{share}%'.format(**{'share': TUNGA_SHARE_PERCENTAGE})
        return {
            'type': 'payment', 'language': 'EN', 'title': self.summary, 'description': self.excerpt or self.summary,
            'keywords': tags, 'participants': [
                {'id': 'mailto:%s' % TUNGA_SHARE_EMAIL, 'role': 'owner', 'share': tunga_share}
            ]
        }

    def mobbr_participation(self, check_only=False):
        participation_meta = self.get_default_participation()
        if not self.url:
            return participation_meta, False

        mobbr_info_url = '%s?url=%s' % ('https://api.mobbr.com/api_v1/uris/info', urllib.quote_plus(self.url))
        r = requests.get(mobbr_info_url, **{'headers': {'Accept': 'application/json'}})
        has_script = False
        if r.status_code == 200:
            response = r.json()
            task_script = response['result']['script']
            for meta_key in participation_meta:
                if meta_key == 'keywords':
                    if isinstance(task_script[meta_key], list):
                        participation_meta[meta_key].extend(task_script[meta_key])
                elif meta_key == 'participants':
                    if isinstance(task_script[meta_key], list):
                        absolute_shares = []
                        relative_shares = []
                        absolute_participants = []
                        relative_participants = []

                        for key, participant in enumerate(task_script[meta_key]):
                            if re.match(r'\d+%$', participant['share']):
                                share = int(participant['share'].replace("%", ""))
                                if share > 0:
                                    absolute_shares.append(share)
                                    new_participant = participant
                                    new_participant['share'] = share
                                    absolute_participants.append(new_participant)
                            else:
                                share = int(participant['share'])
                                if share > 0:
                                    relative_shares.append(share)
                                    new_participant = participant
                                    new_participant['share'] = share
                                    relative_participants.append(new_participant)

                        additional_participants = []
                        total_absolutes = sum(absolute_shares)
                        total_relatives = sum(relative_shares)
                        if total_absolutes >= 100 or total_relatives == 0:
                            additional_participants = absolute_participants
                        elif total_absolutes == 0:
                            additional_participants = relative_participants
                        else:
                            additional_participants = absolute_participants
                            for participant in relative_participants:
                                share = int(round(((participant['share']*(100-total_absolutes))/total_relatives), 0))
                                if share > 0:
                                    new_participant = participant
                                    new_participant['share'] = share
                                    additional_participants.append(new_participant)
                        if len(additional_participants):
                            participation_meta[meta_key].extend(additional_participants)
                            has_script = True
                elif meta_key in task_script:
                    participation_meta[meta_key] = task_script[meta_key]
        return participation_meta, has_script

    @property
    def meta_participation(self):
        participation_meta, has_script = self.mobbr_participation()
        # TODO: Update local participation script to use defined shares
        if not has_script:
            participants = self.participation_set.filter(accepted=True).order_by('share')
            total_shares = 100 - TUNGA_SHARE_PERCENTAGE
            num_participants = participants.count()
            for participant in participants:
                participation_meta['participants'].append(
                    {
                        'id': 'mailto:%s' % participant.user.email,
                        'role': participant.role,
                        'share': int(total_shares/num_participants)
                    }
                )
        return participation_meta


class Application(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    accepted = models.BooleanField(default=False)
    responded = models.BooleanField(default=False)
    pitch = models.CharField(max_length=1000, blank=True, null=True)
    hours_needed = models.PositiveIntegerField(blank=True, null=True)
    hours_available = models.PositiveIntegerField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)  # These will also be delivered as messages to the client
    deliver_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    channels = GenericRelation(Channel, related_query_name='task_applications')

    def __unicode__(self):
        return '%s - %s' % (self.user.get_short_name() or self.user.username, self.task.summary)

    class Meta:
        unique_together = ('user', 'task')

    @staticmethod
    @allow_staff_or_superuser
    def has_read_permission(request):
        return True

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return self.has_object_update_permission(request)

    @staticmethod
    @allow_staff_or_superuser
    def has_write_permission(request):
        return request.user.type == USER_TYPE_DEVELOPER

    @staticmethod
    @allow_staff_or_superuser
    def has_update_permission(request):
        return True

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.user

    @allow_staff_or_superuser
    def has_object_update_permission(self, request):
        # Task owner can update applications
        return request.user == self.user or request.user == self.task.user


class Participation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    accepted = models.BooleanField(default=False)
    responded = models.BooleanField(default=False)
    assignee = models.BooleanField(default=False)
    role = models.CharField(max_length=100, default='Developer')
    share = models.IntegerField(blank=True, null=True)
    satisfaction = models.SmallIntegerField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='participants_added')
    created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(blank=True, null=True)
    ratings = GenericRelation(Rating, related_query_name='participants')

    def __unicode__(self):
        return '%s - %s' % (self.user.get_short_name() or self.user.username, self.task.title)

    class Meta:
        unique_together = ('user', 'task')
        verbose_name_plural = 'participation'

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return self.task.has_object_read_permission(request)

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.user or request.user == self.task.user


TASK_REQUEST_CLOSE = 1
TASK_REQUEST_PAY = 2

TASK_REQUEST_CHOICES = (
    (TASK_REQUEST_CLOSE, 'Close Request'),
    (TASK_REQUEST_PAY, 'Payment Request')
)


class TaskRequest(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    type = models.PositiveSmallIntegerField(
        choices=TASK_REQUEST_CHOICES,
        help_text=','.join(['%s - %s' % (item[0], item[1]) for item in TASK_REQUEST_CHOICES])
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return '%s - %s' % (self.get_type_display(), self.task.summary)

    @staticmethod
    @allow_staff_or_superuser
    def has_read_permission(request):
        return True

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return self.task.has_object_read_permission(request)

    @staticmethod
    @allow_staff_or_superuser
    def has_write_permission(request):
        return request.user.type == USER_TYPE_DEVELOPER

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.user


class SavedTask(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return '%s - %s' % (self.user.get_short_name() or self.user.username, self.task.summary)

    @staticmethod
    @allow_staff_or_superuser
    def has_read_permission(request):
        return True

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return request.user == self.user

    @staticmethod
    @allow_staff_or_superuser
    def has_write_permission(request):
        return request.user.type == USER_TYPE_DEVELOPER

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.user


PROGRESS_EVENT_TYPE_DEFAULT = 1
PROGRESS_EVENT_TYPE_PERIODIC = 2
PROGRESS_EVENT_TYPE_MILESTONE = 3
PROGRESS_EVENT_TYPE_SUBMIT = 4

PROGRESS_EVENT_TYPE_CHOICES = (
    (PROGRESS_EVENT_TYPE_DEFAULT, 'Update'),
    (PROGRESS_EVENT_TYPE_PERIODIC, 'Periodic Update'),
    (PROGRESS_EVENT_TYPE_MILESTONE, 'Milestone'),
    (PROGRESS_EVENT_TYPE_SUBMIT, 'Submission')
)


class ProgressEvent(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    type = models.PositiveSmallIntegerField(
        choices=PROGRESS_EVENT_TYPE_CHOICES, default=PROGRESS_EVENT_TYPE_DEFAULT,
        help_text=','.join(['%s - %s' % (item[0], item[1]) for item in PROGRESS_EVENT_TYPE_CHOICES])
    )
    due_at = models.DateTimeField()
    title = models.CharField(max_length=200, blank=True, null=True)
    description = models.CharField(max_length=1000, blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='progress_events_created', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_reminder_at = models.DateTimeField(blank=True, null=True)

    def __unicode__(self):
        return '%s | %s - %s' % (self.get_type_display(), self.task.summary, self.due_at)

    class Meta:
        unique_together = ('task', 'due_at')
        ordering = ['due_at']

    @staticmethod
    @allow_staff_or_superuser
    def has_read_permission(request):
        return True

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return self.task.has_object_read_permission(request)

    @staticmethod
    @allow_staff_or_superuser
    def has_write_permission(request):
        return request.user.type == USER_TYPE_PROJECT_OWNER

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.task.user


PROGRESS_REPORT_STATUS_ON_SCHEDULE = 1
PROGRESS_REPORT_STATUS_BEHIND = 2
PROGRESS_REPORT_STATUS_STUCK = 3

PROGRESS_REPORT_STATUS_CHOICES = (
    (PROGRESS_REPORT_STATUS_ON_SCHEDULE, 'On schedule'),
    (PROGRESS_REPORT_STATUS_BEHIND, 'Behind'),
    (PROGRESS_REPORT_STATUS_STUCK, 'Stuck')
)


class ProgressReport(models.Model):
    event = models.OneToOneField(ProgressEvent, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING)
    status = models.PositiveSmallIntegerField(
        choices=PROGRESS_REPORT_STATUS_CHOICES,
        help_text=','.join(['%s - %s' % (item[0], item[1]) for item in PROGRESS_REPORT_STATUS_CHOICES])
    )
    percentage = models.PositiveIntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)])
    accomplished = models.TextField()
    next_steps = models.TextField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    uploads = GenericRelation(Upload, related_query_name='progress_reports')

    def __unicode__(self):
        return '{0} - {1}%'.format(self.event, self.percentage)

    @staticmethod
    @allow_staff_or_superuser
    def has_read_permission(request):
        return True

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return self.event.task.has_object_read_permission(request)

    @staticmethod
    @allow_staff_or_superuser
    def has_write_permission(request):
        return request.user.type == USER_TYPE_DEVELOPER

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.user


class IntegrationEvent(models.Model):
    id = models.CharField(max_length=30, primary_key=True)
    name = models.CharField(max_length=30)
    description = models.CharField(max_length=200, blank=True, null=True)
    created_by = models.ForeignKey(
            settings.AUTH_USER_MODEL, blank=True, null=True, related_name='integration_events_created',
            on_delete=models.DO_NOTHING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return '%s - %s' % (self.id, self.name)

    class Meta:
        ordering = ['id', 'name']


INTEGRATION_TYPE_REPO = 1
INTEGRATION_TYPE_ISSUE = 2

INTEGRATION_TYPE_CHOICES = (
    (INTEGRATION_TYPE_REPO, 'Repo'),
    (INTEGRATION_TYPE_ISSUE, 'Issue')
)


class Integration(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    provider = models.CharField(max_length=30, choices=providers.registry.as_choices())
    type = models.PositiveSmallIntegerField(
        choices=INTEGRATION_TYPE_CHOICES,
        help_text=','.join(['%s - %s' % (item[0], item[1]) for item in INTEGRATION_TYPE_CHOICES])
    )
    events = models.ManyToManyField(IntegrationEvent, related_name='integrations')
    secret = models.CharField(max_length=30, default=get_random_string)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='integrations_created', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return '%s - %s' % (self.get_provider_display(), self.task.summary)

    class Meta:
        unique_together = ('task', 'provider')
        ordering = ['created_at']

    @staticmethod
    @allow_staff_or_superuser
    def has_read_permission(request):
        return True

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return request.user == self.task.user

    @staticmethod
    @allow_staff_or_superuser
    def has_write_permission(request):
        return request.user.type == USER_TYPE_PROJECT_OWNER

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user == self.task.user

    @property
    def hook_id(self):
        try:
            return self.integrationmeta_set.get(meta_key='hook_id').meta_value
        except:
            return None

    @property
    def repo_id(self):
        try:
            return self.integrationmeta_set.get(meta_key='repo_id').meta_value
        except:
            return None

    @property
    def repo_full_name(self):
        try:
            return self.integrationmeta_set.get(meta_key='repo_full_name').meta_value
        except:
            return None

    @property
    def issue_id(self):
        try:
            return self.integrationmeta_set.get(meta_key='issue_id').meta_value
        except:
            return None

    @property
    def issue_number(self):
        try:
            return self.integrationmeta_set.get(meta_key='issue_number').meta_value
        except:
            return None

class IntegrationMeta(models.Model):
    integration = models.ForeignKey(Integration, on_delete=models.CASCADE)
    meta_key = models.CharField(max_length=30)
    meta_value = models.CharField(max_length=30)
    created_by = models.ForeignKey(
            settings.AUTH_USER_MODEL, related_name='integration_meta_created', blank=True, null=True,
            on_delete=models.DO_NOTHING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return '%s | %s - %s' % (self.integration, self.meta_key, self.meta_value)

    class Meta:
        ordering = ['created_at']


class IntegrationActivity(models.Model):
    integration = models.ForeignKey(Integration, on_delete=models.CASCADE, related_name='activities')
    event = models.ForeignKey(IntegrationEvent, related_name='integration_activities')
    action = models.CharField(max_length=30, blank=True, null=True)
    url = models.URLField(blank=True, null=True)
    ref = models.CharField(max_length=30, blank=True, null=True)
    ref_name = models.CharField(max_length=50, blank=True, null=True)
    username = models.CharField(max_length=30, blank=True, null=True)
    fullname = models.CharField(max_length=50, blank=True, null=True)
    avatar_url = models.URLField(blank=True, null=True)
    title = models.CharField(max_length=200,blank=True, null=True)
    body = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return '%s | ' % (self.integration, )

    class Meta:
        ordering = ['created_at']
