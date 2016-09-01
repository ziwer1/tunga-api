# encoding=utf8
from __future__ import unicode_literals

import uuid
from decimal import Decimal

import tagulous.models
from actstream.models import Action
from allauth.socialaccount import providers
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.query_utils import Q
from django.template.defaultfilters import floatformat
from django.utils.crypto import get_random_string
from django.utils.html import strip_tags
from dry_rest_permissions.generics import allow_staff_or_superuser

from tunga import settings
from tunga.settings import TUNGA_SHARE_PERCENTAGE, BITONIC_PAYMENT_COST_PERCENTAGE, \
    BANK_TRANSFER_PAYMENT_COST_PERCENTAGE
from tunga_activity.models import ActivityReadLog
from tunga_auth.models import USER_TYPE_DEVELOPER, USER_TYPE_PROJECT_OWNER
from tunga_comments.models import Comment
from tunga_messages.models import Channel
from tunga_profiles.models import Skill, Connection
from tunga_settings.models import VISIBILITY_DEVELOPER, VISIBILITY_MY_TEAM, VISIBILITY_CUSTOM, VISIBILITY_CHOICES
from tunga_utils.models import Upload, Rating
from tunga_utils.validators import validate_btc_address

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

    archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(blank=True, null=True)

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


TASK_PAYMENT_METHOD_BITONIC = 'bitonic'
TASK_PAYMENT_METHOD_BITCOIN = 'bitcoin'
TASK_PAYMENT_METHOD_BANK = 'bank'

TASK_PAYMENT_METHOD_CHOICES = (
    (TASK_PAYMENT_METHOD_BITONIC, 'Pay with ideal / mister cash'),
    (TASK_PAYMENT_METHOD_BITCOIN, 'Pay with bitcoin'),
    (TASK_PAYMENT_METHOD_BANK, 'Pay by bank transfer')
)


class Task(models.Model):
    project = models.ForeignKey(Project, related_name='tasks', on_delete=models.SET_NULL, blank=True, null=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='tasks_created', on_delete=models.DO_NOTHING)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    url = models.URLField(blank=True, null=True)
    fee = models.DecimalField(
        max_digits=19, decimal_places=4, validators=[MinValueValidator(15, message='Minimum pledge amount is EUR 15')]
    )
    currency = models.CharField(max_length=5, choices=CURRENCY_CHOICES, default=CURRENCY_CHOICES[0][0])
    deadline = models.DateTimeField(blank=True, null=True)
    skills = tagulous.models.TagField(Skill, blank=True)
    visibility = models.PositiveSmallIntegerField(choices=VISIBILITY_CHOICES, default=VISIBILITY_CHOICES[0][0])
    update_interval = models.PositiveIntegerField(blank=True, null=True)
    update_interval_units = models.PositiveSmallIntegerField(choices=UPDATE_SCHEDULE_CHOICES, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    apply = models.BooleanField(default=True)
    applicants = models.ManyToManyField(
            settings.AUTH_USER_MODEL, through='Application', through_fields=('task', 'user'),
            related_name='task_applications', blank=True
    )
    apply_closed_at = models.DateTimeField(blank=True, null=True)

    participants = models.ManyToManyField(
            settings.AUTH_USER_MODEL, through='Participation', through_fields=('task', 'user'),
            related_name='task_participants', blank=True)

    closed = models.BooleanField(default=False)
    closed_at = models.DateTimeField(blank=True, null=True)
    satisfaction = models.SmallIntegerField(blank=True, null=True)

    paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(blank=True, null=True)

    payment_method = models.CharField(
        max_length=30, choices=TASK_PAYMENT_METHOD_CHOICES,
        help_text=','.join(['%s - %s' % (item[0], item[1]) for item in TASK_PAYMENT_METHOD_CHOICES]),
        blank=True, null=True
    )
    invoice_date = models.DateTimeField(blank=True, null=True)
    btc_address = models.CharField(max_length=40, blank=True, null=True, validators=[validate_btc_address])
    btc_price = models.DecimalField(max_digits=18, decimal_places=8, blank=True, null=True)
    pay_distributed = models.BooleanField(default=False)

    archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(blank=True, null=True)

    comments = GenericRelation(Comment, related_query_name='tasks')
    uploads = GenericRelation(Upload, related_query_name='tasks')
    ratings = GenericRelation(Rating, related_query_name='tasks')
    activity_objects = GenericRelation(
        Action,
        object_id_field='target_object_id',
        content_type_field='target_content_type',
        related_query_name='tasks'
    )
    read_logs = GenericRelation(ActivityReadLog, related_query_name='tasks')

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
        if request.user == self.user:
            return True
        elif self.visibility == VISIBILITY_DEVELOPER:
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
            allowed_keys = ['assignee', 'participation', 'participants', 'confirmed_participants', 'rejected_participants']
            if not [x for x in request.data.keys() if not x in allowed_keys]:
                return self.participation_set.filter((Q(accepted=True) | Q(responded=False)), user=request.user).count()
        return False

    @property
    def task_number(self):
        return 'A{:03d}'.format(self.id)

    def display_fee(self, amount=None):
        if amount is None:
            amount = self.fee
        if self.currency in CURRENCY_SYMBOLS:
            return '%s%s' % (CURRENCY_SYMBOLS[self.currency], floatformat(amount, arg=-2))
        return amount

    @property
    def amount(self):
        tunga_share = TUNGA_SHARE_PERCENTAGE * 0.01
        dev_share = 1 - tunga_share
        processing_share = 0
        if self.payment_method == TASK_PAYMENT_METHOD_BITONIC:
            processing_share = BITONIC_PAYMENT_COST_PERCENTAGE * 0.01
        elif self.payment_method == TASK_PAYMENT_METHOD_BANK:
            processing_share = BANK_TRANSFER_PAYMENT_COST_PERCENTAGE * 0.01
        amount_details = {
            'currency': CURRENCY_SYMBOLS.get(self.currency, ''),
            'pledge': self.fee,
            'developer': Decimal(dev_share) * self.fee,
            'tunga': Decimal(tunga_share) * self.fee,
            'processing': Decimal(processing_share) * self.fee
        }

        amount_details['total'] = amount_details['developer'] + amount_details['tunga'] + amount_details['processing']
        return amount_details

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

    def payment_status(self):
        return self.paid and self.pay_distributed and 'Paid' or self.paid and 'Processing' or 'Pending'

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
    def invoice(self):
        try:
            return self.taskinvoice_set.all().order_by('-id', '-created_at').first()
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
    def activity_stream(self):
        return Action.objects.filter(Q(tasks=self) | Q(progress_events__task=self))

    def get_participation_shares(self):
        participants = self.participation_set.filter(accepted=True).order_by('-share')
        num_participants = participants.count()

        participation_shares = []

        if participants:
            all_shares = [participant.share or 0 for participant in participants]
            total_shares = all_shares and sum(all_shares) or 0

            for participant in participants:
                if not total_shares:
                    share = 1/Decimal(num_participants)
                else:
                    share = Decimal(participant.share or 0)/Decimal(total_shares)
                participation_shares.append({
                    'participant': participant,
                    'share': share
                })
        return participation_shares

    def get_payment_shares(self):
        participation_shares = self.get_participation_shares()
        total_shares = 100 - TUNGA_SHARE_PERCENTAGE
        share_fraction = Decimal(total_shares)/Decimal(100)

        payment_shares = []

        if participation_shares:
            for data in participation_shares:
                payment_shares.append({
                    'participant': data['participant'],
                    'share': Decimal(data['share'])*share_fraction
                })
        return payment_shares


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
    share = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    satisfaction = models.SmallIntegerField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='participants_added')
    created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(blank=True, null=True)
    paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(blank=True, null=True)

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

    activity_objects = GenericRelation(
        Action,
        object_id_field='target_object_id',
        content_type_field='target_content_type',
        related_query_name='progress_events'
    )

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
    title = models.CharField(max_length=200, blank=True, null=True)
    body = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return '%s | ' % (self.integration, )

    class Meta:
        ordering = ['created_at']


class TaskPayment(models.Model):
    task = models.ForeignKey(Task)
    btc_address = models.CharField(max_length=40, validators=[validate_btc_address])
    ref = models.CharField(max_length=255)
    btc_price = models.DecimalField(max_digits=18, decimal_places=8)
    btc_received = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    received_at = models.DateTimeField(blank=True, null=True)

    def __unicode__(self):
        return 'bitcoin:%s - %s' % (self.btc_address, self.task.summary)

    class Meta:
        unique_together = ('btc_address', 'ref')
        ordering = ['created_at']


PAYMENT_STATUS_PENDING = 'pending'
PAYMENT_STATUS_PROCESSING = 'processing'
PAYMENT_STATUS_COMPLETED = 'completed'
PAYMENT_STATUS_FAILED = 'failed'

PAYMENT_STATUS_CHOICES = (
    (PAYMENT_STATUS_PENDING, 'Pending'),
    (PAYMENT_STATUS_PROCESSING, 'Processing'),
    (PAYMENT_STATUS_COMPLETED, 'Completed'),
    (PAYMENT_STATUS_FAILED, 'Failed'),
)


class ParticipantPayment(models.Model):
    participant = models.ForeignKey(Participation)
    source = models.ForeignKey(TaskPayment)
    destination = models.CharField(max_length=40, validators=[validate_btc_address])
    idem_key = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    ref = models.CharField(max_length=255)
    btc_sent = models.DecimalField(max_digits=18, decimal_places=8, blank=True, null=True)
    btc_received = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    status = models.CharField(
        max_length=30, choices=PAYMENT_STATUS_CHOICES, default=PAYMENT_STATUS_PENDING,
        help_text=', '.join(['%s - %s' % (item[0], item[1]) for item in PAYMENT_STATUS_CHOICES])
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    received_at = models.DateTimeField(blank=True, null=True)
    description = models.CharField(max_length=200, blank=True, null=True)

    def __unicode__(self):
        return 'bitcoin:%s - %s | %s' % (self.destination, self.participant.user, self.description)

    class Meta:
        unique_together = ('participant', 'source')
        ordering = ['created_at']


class TaskInvoice(models.Model):
    task = models.ForeignKey(Task)
    title = models.CharField(max_length=200)
    fee = models.DecimalField(max_digits=19, decimal_places=4)
    client = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='client_invoices')
    developer = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='developer_invoices')
    currency = models.CharField(max_length=5, choices=CURRENCY_CHOICES, default=CURRENCY_CHOICES[0][0])
    payment_method = models.CharField(
        max_length=30, choices=TASK_PAYMENT_METHOD_CHOICES,
        help_text=','.join(['%s - %s' % (item[0], item[1]) for item in TASK_PAYMENT_METHOD_CHOICES])
    )
    btc_address = models.CharField(max_length=40, validators=[validate_btc_address])
    btc_price = models.DecimalField(max_digits=18, decimal_places=8, blank=True, null=True)
    number = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return self.summary

    class Meta:
        ordering = ['created_at']

    def display_fee(self, amount=None):
        if amount is None:
            amount = self.fee
        if self.currency in CURRENCY_SYMBOLS:
            return '%s%s' % (CURRENCY_SYMBOLS[self.currency], floatformat(amount, arg=-2))
        return amount

    @property
    def amount(self):
        tunga_share = TUNGA_SHARE_PERCENTAGE * 0.01
        dev_share = 1 - tunga_share
        processing_share = 0
        if self.payment_method == TASK_PAYMENT_METHOD_BITONIC:
            processing_share = BITONIC_PAYMENT_COST_PERCENTAGE * 0.01
        elif self.payment_method == TASK_PAYMENT_METHOD_BANK:
            processing_share = BANK_TRANSFER_PAYMENT_COST_PERCENTAGE * 0.01
        amount_details = {
            'currency': CURRENCY_SYMBOLS.get(self.currency, ''),
            'pledge': self.fee,
            'developer': Decimal(dev_share) * self.fee,
            'tunga': Decimal(tunga_share) * self.fee,
            'processing': Decimal(processing_share) * self.fee
        }

        amount_details['total'] = amount_details['pledge'] + amount_details['processing']
        amount_details['total_dev'] = amount_details['tunga'] + amount_details['processing']
        return amount_details

    @property
    def summary(self):
        return self.number or '%s - Fee: %s' % (self.title, self.display_fee())
