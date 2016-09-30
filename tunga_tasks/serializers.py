import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db.models.query_utils import Q
from django.template.defaultfilters import floatformat
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from tunga.settings import TUNGA_SHARE_PERCENTAGE
from tunga_auth.serializers import UserSerializer
from tunga_profiles.utils import profile_check
from tunga_tasks import slugs
from tunga_tasks.notifications import send_new_task_email
from tunga_tasks.models import Task, Application, Participation, TaskRequest, SavedTask, ProgressEvent, ProgressReport, \
    Project, IntegrationMeta, Integration, IntegrationEvent, IntegrationActivity, TASK_PAYMENT_METHOD_CHOICES, \
    TaskInvoice
from tunga_utils.constants import PROGRESS_EVENT_TYPE_MILESTONE
from tunga_tasks.signals import application_response, participation_response, task_applications_closed, task_closed
from tunga_utils.mixins import GetCurrentUserAnnotatedSerializerMixin
from tunga_utils.models import Rating
from tunga_utils.serializers import ContentTypeAnnotatedModelSerializer, SkillSerializer, \
    CreateOnlyCurrentUserDefault, SimpleUserSerializer, UploadSerializer, DetailAnnotatedModelSerializer, \
    SimpleRatingSerializer, InvoiceUserSerializer


class SimpleProjectSerializer(ContentTypeAnnotatedModelSerializer):
    user = SimpleUserSerializer()

    class Meta:
        model = Project


class SimpleTaskSerializer(ContentTypeAnnotatedModelSerializer):
    user = SimpleUserSerializer()

    class Meta:
        model = Task
        fields = ('id', 'user', 'title', 'currency', 'fee', 'closed', 'paid', 'display_fee')


class SimpleApplicationSerializer(ContentTypeAnnotatedModelSerializer):
    user = SimpleUserSerializer()

    class Meta:
        model = Application
        exclude = ('created_at',)


class SimpleParticipationSerializer(ContentTypeAnnotatedModelSerializer):
    user = SimpleUserSerializer()

    class Meta:
        model = Participation
        exclude = ('created_at',)


class BasicProgressEventSerializer(ContentTypeAnnotatedModelSerializer):
    created_by = SimpleUserSerializer()

    class Meta:
        model = ProgressEvent


class BasicProgressReportSerializer(ContentTypeAnnotatedModelSerializer):
    user = SimpleUserSerializer()
    status_display = serializers.CharField(required=False, read_only=True, source='get_status_display')

    class Meta:
        model = ProgressReport


class SimpleProgressEventSerializer(BasicProgressEventSerializer):
    report = BasicProgressReportSerializer(read_only=True, required=False, source='progressreport')

    class Meta:
        model = ProgressEvent


class SimpleProgressReportSerializer(BasicProgressReportSerializer):
    uploads = UploadSerializer(required=False, read_only=True, many=True)

    class Meta:
        model = ProgressReport


class NestedTaskParticipationSerializer(ContentTypeAnnotatedModelSerializer):
    created_by = SimpleUserSerializer(
        required=False, read_only=True, default=CreateOnlyCurrentUserDefault()
    )

    class Meta:
        model = Participation
        exclude = ('task', 'created_at')


class NestedProgressEventSerializer(ContentTypeAnnotatedModelSerializer):
    created_by = SimpleUserSerializer(
        required=False, read_only=True, default=CreateOnlyCurrentUserDefault()
    )
    report = BasicProgressReportSerializer(read_only=True, required=False, source='progressreport')

    class Meta:
        model = ProgressEvent
        exclude = ('task', 'created_at')


class ProjectDetailsSerializer(ContentTypeAnnotatedModelSerializer):
    user = SimpleUserSerializer()
    tasks = SimpleTaskSerializer(many=True)

    class Meta:
        model = Project
        fields = ('user', 'tasks')


class ProjectSerializer(ContentTypeAnnotatedModelSerializer, DetailAnnotatedModelSerializer):
    user = SimpleUserSerializer(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())
    excerpt = serializers.CharField(required=False, read_only=True)
    deadline = serializers.DateTimeField(required=False, allow_null=True)
    tasks = serializers.PrimaryKeyRelatedField(required=False, read_only=True, many=True)

    class Meta:
        model = Project
        read_only_fields = ('created_at',)
        details_serializer = ProjectDetailsSerializer


class TaskPaymentSerializer(serializers.ModelSerializer):
    user = InvoiceUserSerializer(required=False, read_only=True)
    payment_method = serializers.ChoiceField(choices=TASK_PAYMENT_METHOD_CHOICES, required=True)

    class Meta:
        model = Task
        fields = (
            'id', 'user', 'title', 'summary', 'currency', 'fee', 'payment_method', 'btc_address', 'btc_price'
        )
        read_only_fields = ('title', 'summary', 'currency', 'btc_address', 'btc_price')
        extra_kwargs = {'fee': {'required': True}}


class TaskInvoiceSerializer(serializers.ModelSerializer, GetCurrentUserAnnotatedSerializerMixin):
    client = InvoiceUserSerializer(required=False, read_only=True)
    developer = InvoiceUserSerializer(required=False, read_only=True)
    amount = serializers.JSONField(required=False, read_only=True)
    developer_amount = serializers.SerializerMethodField(required=False, read_only=True)

    class Meta:
        model = TaskInvoice

    def get_developer_amount(self, obj):
        current_user = self.get_current_user()
        if current_user and current_user.is_developer:
            participation = obj.task.participation_set.get(user=current_user)
            share = obj.task.get_user_participation_share(participation.id)
            return obj.get_amount_details(share=share)
        return obj.get_amount_details(share=0)


class ParticipantShareSerializer(serializers.Serializer):
    participant = SimpleParticipationSerializer()
    share = serializers.DecimalField(max_digits=5, decimal_places=2)
    percentage = serializers.SerializerMethodField()
    display_share = serializers.SerializerMethodField()

    def get_percentage(self, obj):
        return floatformat(obj['share']*100, -2)

    def get_display_share(self, obj):
        return floatformat(obj['share']*100)


class TaskDetailsSerializer(ContentTypeAnnotatedModelSerializer):
    project = SimpleProjectSerializer()
    skills = SkillSerializer(many=True)
    applications = SimpleApplicationSerializer(many=True, source='application_set')
    participation = SimpleParticipationSerializer(many=True, source='participation_set')
    participation_shares = ParticipantShareSerializer(many=True, source='get_participation_shares')

    class Meta:
        model = Task
        fields = ('project', 'amount', 'skills', 'applications', 'participation', 'participation_shares')


class TaskSerializer(ContentTypeAnnotatedModelSerializer, DetailAnnotatedModelSerializer,
                     GetCurrentUserAnnotatedSerializerMixin):
    user = SimpleUserSerializer(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())
    display_fee = serializers.SerializerMethodField(required=False, read_only=True)
    amount = serializers.JSONField(required=False, read_only=True)
    excerpt = serializers.CharField(required=False, read_only=True)
    skills = serializers.CharField(required=True, allow_blank=True, allow_null=True)
    payment_status = serializers.CharField(required=False, read_only=True)
    deadline = serializers.DateTimeField(required=False, allow_null=True)
    can_apply = serializers.SerializerMethodField(read_only=True, required=False)
    can_save = serializers.SerializerMethodField(read_only=True, required=False)
    is_participant = serializers.SerializerMethodField(read_only=True, required=False)
    my_participation = serializers.SerializerMethodField(read_only=True, required=False)
    summary = serializers.CharField(read_only=True, required=False)
    assignee = SimpleParticipationSerializer(required=False, read_only=True)
    participants = serializers.PrimaryKeyRelatedField(
        many=True, queryset=get_user_model().objects.all(), required=False, write_only=True
    )
    update_schedule_display = serializers.CharField(required=False, read_only=True)
    participation = NestedTaskParticipationSerializer(required=False, read_only=False, many=True)
    milestones = NestedProgressEventSerializer(required=False, read_only=False, many=True)
    progress_events = NestedProgressEventSerializer(required=False, read_only=True, many=True)
    ratings = SimpleRatingSerializer(required=False, read_only=False, many=True)
    uploads = UploadSerializer(required=False, read_only=True, many=True)
    all_uploads = UploadSerializer(required=False, read_only=True, many=True)
    invoice = TaskInvoiceSerializer(required=False, read_only=True)

    class Meta:
        model = Task
        exclude = ('applicants',)
        read_only_fields = (
            'created_at', 'paid', 'paid_at', 'invoice_date', 'btc_address', 'btc_price', 'pay_distributed'
        )
        details_serializer = TaskDetailsSerializer

    def create(self, validated_data):

        current_user = self.get_current_user()
        if not profile_check(current_user):
            ValidationError('You need complete your profile before you can post tasks')

        skills = None
        participation = None
        milestones = None
        participants = None
        ratings = None
        if 'skills' in validated_data:
            skills = validated_data.pop('skills')
        if 'participation' in validated_data:
            participation = validated_data.pop('participation')
        if 'milestones' in validated_data:
            milestones = validated_data.pop('milestones')
        if 'participants' in validated_data:
            participants = validated_data.pop('participants')
        if 'ratings' in validated_data:
            ratings = validated_data.pop('ratings')

        if participation or participants:
            # close applications if paticipants are provided
            validated_data['apply'] = False
        instance = super(TaskSerializer, self).create(validated_data)
        self.save_skills(instance, skills)
        self.save_participants(instance, participants)
        self.save_participation(instance, participation)
        self.save_milestones(instance, milestones)
        self.save_ratings(instance, ratings)

        # Triggered here instead of in the post_save signal to allow skills to be attached first
        # TODO: Consider moving this trigger
        send_new_task_email.delay(instance.id)
        return instance

    def update(self, instance, validated_data):

        if 'fee' in validated_data and validated_data['fee'] < instance.fee:
            raise ValidationError({
                'fee': 'You cannot reduce the fee for the task, Please contact support@tunga.io for assistance'
            })

        initial_apply = instance.apply
        initial_closed = instance.closed

        skills = None
        participation = None
        milestones = None
        participants = None
        ratings = None
        if 'skills' in validated_data:
            skills = validated_data.pop('skills')
        if 'participation' in validated_data:
            participation = validated_data.pop('participation')
        if 'milestones' in validated_data:
            milestones = validated_data.pop('milestones')
        if 'participants' in validated_data:
            participants = validated_data.pop('participants')
        if 'ratings' in validated_data:
            ratings = validated_data.pop('ratings')

        if not instance.closed and validated_data.get('closed'):
            validated_data['closed_at'] = datetime.datetime.utcnow()

        if not instance.paid and validated_data.get('paid'):
            validated_data['paid_at'] = datetime.datetime.utcnow()

        instance = super(TaskSerializer, self).update(instance, validated_data)
        self.save_skills(instance, skills)
        self.save_participants(instance, participants)
        self.save_participation(instance, participation)
        self.save_milestones(instance, milestones)
        self.save_ratings(instance, ratings)

        if initial_apply and not instance.apply:
            task_applications_closed.send(sender=Task, task=instance)

        if not initial_closed and instance.closed:
            task_closed.send(sender=Task, task=instance)
        return instance

    def save_skills(self, task, skills):
        if skills is not None:
            task.skills = skills
            task.save()

    def save_participation(self, task, participation):
        if participation:
            new_assignee = None
            for item in participation:
                if item.get('accepted', False):
                    item['activated_at'] = datetime.datetime.utcnow()
                defaults = item
                if isinstance(defaults, dict):
                    defaults['created_by'] = task.user

                try:
                    participation_obj, created = Participation.objects.update_or_create(
                        task=task, user=item['user'], defaults=defaults)
                    if not created:
                        participation_response.send(sender=Participation, participation=participation_obj)
                    if 'assignee' in item and item['assignee']:
                        new_assignee = item['user']
                except:
                    pass
            if new_assignee:
                Participation.objects.exclude(user=new_assignee).filter(task=task).update(assignee=False)

    def save_milestones(self, task, milestones):
        if milestones:
            for item in milestones:
                event_type = item.get('type', PROGRESS_EVENT_TYPE_MILESTONE)
                if event_type != PROGRESS_EVENT_TYPE_MILESTONE:
                    continue
                defaults = {'created_by': self.get_current_user() or task.user}
                defaults.update(item)
                try:
                    ProgressEvent.objects.update_or_create(
                        task=task, type=event_type, due_at=item['due_at'], defaults=defaults
                    )
                except:
                    pass

    def save_ratings(self, task, ratings):
        if ratings:
            for item in ratings:
                try:
                    Rating.objects.update_or_create(content_type=ContentType.objects.get_for_model(task),
                                                    object_id=task.id, criteria=item['criteria'], defaults=item)
                except:
                    pass

    def save_participants(self, task, participants):
        # TODO: Remove and move existing code to using save_participation
        if participants:
            assignee = self.initial_data.get('assignee', None)
            confirmed_participants = self.initial_data.get('confirmed_participants', None)
            rejected_participants = self.initial_data.get('rejected_participants', None)
            created_by = task.user

            changed_assignee = False
            for user in participants:
                try:
                    defaults = {'created_by': created_by}
                    if assignee:
                        defaults['assignee'] = bool(user.id == assignee)
                    if rejected_participants and user.id in rejected_participants:
                        defaults['accepted'] = False
                        defaults['responded'] = True
                    if confirmed_participants and user.id in confirmed_participants:
                        defaults['accepted'] = True
                        defaults['responded'] = True
                        defaults['activated_at'] = datetime.datetime.utcnow()

                    participation_obj, created = Participation.objects.update_or_create(
                        task=task, user=user, defaults=defaults)
                    if not created:
                        participation_response.send(sender=Participation, participation=participation_obj)
                    if user.id == assignee:
                        changed_assignee = True
                except:
                    pass
            if assignee and changed_assignee:
                Participation.objects.exclude(user__id=assignee).filter(task=task).update(assignee=False)

    def get_display_fee(self, obj):
        user = self.get_current_user()
        amount = None
        if user and user.is_developer:
            amount = obj.fee * (1 - Decimal(TUNGA_SHARE_PERCENTAGE) * Decimal(0.01))
        return obj.display_fee(amount=amount)

    def get_can_apply(self, obj):
        if obj.closed or not obj.apply:
            return False
        user = self.get_current_user()
        if user:
            if obj.user == user or user.pending or not profile_check(user):
                return False
            return obj.applicants.filter(id=user.id).count() == 0 and \
                   obj.participation_set.filter(user=user).count() == 0
        return False

    def get_can_save(self, obj):
        user = self.get_current_user()
        if user:
            if obj.user == user:
                return False
            return obj.savedtask_set.filter(user=user).count() == 0
        return False

    def get_is_participant(self, obj):
        user = self.get_current_user()
        if user:
            return obj.participation_set.filter((Q(accepted=True) | Q(responded=False)), user=user).count() == 1
        return False

    def get_my_participation(self, obj):
        user = self.get_current_user()
        if user:
            try:
                participation = obj.participation_set.get(user=user)
                return {
                    'id': participation.id,
                    'user': participation.user.id,
                    'assignee': participation.assignee,
                    'accepted': participation.accepted,
                    'responded': participation.responded
                }
            except:
                pass
        return None


class ApplicationDetailsSerializer(SimpleApplicationSerializer):
    user = UserSerializer()
    task = SimpleTaskSerializer()

    class Meta:
        model = Application
        fields = ('user', 'task')


class ApplicationSerializer(ContentTypeAnnotatedModelSerializer, DetailAnnotatedModelSerializer):
    user = SimpleUserSerializer(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())

    class Meta:
        model = Application
        details_serializer = ApplicationDetailsSerializer
        extra_kwargs = {
            'pitch': {'required': True, 'allow_blank': False, 'allow_null': False},
            #'hours_needed': {'required': True, 'allow_null': False},
            #'hours_available': {'required': True, 'allow_null': False},
            'deliver_at': {'required': True, 'allow_null': False}
        }

    def update(self, instance, validated_data):
        initial_responded = instance.responded
        if validated_data.get('accepted'):
            validated_data['responded'] = True
        instance = super(ApplicationSerializer, self).update(instance, validated_data)
        if not initial_responded and instance.accepted or instance.responded:
            application_response.send(sender=Application, application=instance)
        return instance


class ParticipationDetailsSerializer(SimpleParticipationSerializer):
    created_by = SimpleUserSerializer()
    task = SimpleTaskSerializer()

    class Meta:
        model = Participation
        fields = ('user', 'task', 'created_by')


class ParticipationSerializer(ContentTypeAnnotatedModelSerializer, DetailAnnotatedModelSerializer):
    created_by = SimpleUserSerializer(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())

    class Meta:
        model = Participation
        read_only_fields = ('created_at',)
        details_serializer = ParticipationDetailsSerializer

    def update(self, instance, validated_data):
        initial_responded = instance.responded
        if validated_data.get('accepted'):
            validated_data['responded'] = True
            validated_data['activated_at'] = datetime.datetime.utcnow()
        instance = super(ParticipationSerializer, self).update(instance, validated_data)
        if not initial_responded and instance.accepted or instance.responded:
            participation_response.send(sender=Participation, participation=instance)
        return instance


class TaskRequestDetailsSerializer(serializers.ModelSerializer):
    user = SimpleUserSerializer()
    task = SimpleTaskSerializer()

    class Meta:
        model = TaskRequest
        fields = ('user', 'task')


class TaskRequestSerializer(ContentTypeAnnotatedModelSerializer, DetailAnnotatedModelSerializer):
    user = SimpleUserSerializer(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())

    class Meta:
        model = TaskRequest
        read_only_fields = ('created_at',)
        details_serializer = TaskRequestDetailsSerializer


class SavedTaskDetailsSerializer(serializers.ModelSerializer):
    user = SimpleUserSerializer()
    task = SimpleTaskSerializer()

    class Meta:
        model = SavedTask
        fields = ('user', 'task')


class SavedTaskSerializer(ContentTypeAnnotatedModelSerializer, DetailAnnotatedModelSerializer):
    user = SimpleUserSerializer(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())

    class Meta:
        model = SavedTask
        read_only_fields = ('created_at',)
        details_serializer = SavedTaskDetailsSerializer


class ProgressEventDetailsSerializer(serializers.ModelSerializer):
    task = SimpleTaskSerializer()
    created_by = SimpleUserSerializer()

    class Meta:
        model = ProgressEvent
        fields = ('task', 'created_by')


class ProgressEventSerializer(ContentTypeAnnotatedModelSerializer, DetailAnnotatedModelSerializer):
    created_by = SimpleUserSerializer(required=False, read_only=True,
                                                    default=CreateOnlyCurrentUserDefault())
    report = SimpleProgressReportSerializer(read_only=True, required=False, source='progressreport')

    class Meta:
        model = ProgressEvent
        read_only_fields = ('created_at',)
        details_serializer = ProgressEventDetailsSerializer


class ProgressReportDetailsSerializer(serializers.ModelSerializer):
    event = BasicProgressEventSerializer()

    class Meta:
        model = SavedTask
        fields = ('event',)


class ProgressReportSerializer(ContentTypeAnnotatedModelSerializer, DetailAnnotatedModelSerializer):
    user = SimpleUserSerializer(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())
    status_display = serializers.CharField(required=False, read_only=True, source='get_status_display')
    uploads = UploadSerializer(required=False, read_only=True, many=True)

    class Meta:
        model = ProgressReport
        read_only_fields = ('created_at',)
        details_serializer = ProgressReportDetailsSerializer


class NestedIntegrationMetaSerializer(serializers.ModelSerializer):
    created_by = SimpleUserSerializer(
        required=False, read_only=True, default=CreateOnlyCurrentUserDefault()
    )

    class Meta:
        model = IntegrationMeta
        exclude = ('integration', 'created_at', 'updated_at')


class SimpleIntegrationSerializer(ContentTypeAnnotatedModelSerializer):
    class Meta:
        model = Integration
        exclude = ('secret',)


class IntegrationSerializer(ContentTypeAnnotatedModelSerializer, GetCurrentUserAnnotatedSerializerMixin):
    created_by = SimpleUserSerializer(
        required=False, read_only=True, default=CreateOnlyCurrentUserDefault()
    )
    events = serializers.PrimaryKeyRelatedField(
        many=True, queryset=IntegrationEvent.objects.all(), required=False, read_only=False
    )
    meta = NestedIntegrationMetaSerializer(required=False, read_only=False, many=True, source='integrationmeta_set')
    repo = serializers.JSONField(required=False, write_only=True, allow_null=True)
    issue = serializers.JSONField(required=False, write_only=True, allow_null=True)
    repo_id = serializers.CharField(required=False, read_only=True)
    issue_id = serializers.CharField(required=False, read_only=True)

    class Meta:
        model = Integration
        exclude = ('secret',)
        read_only_fields = ('created_at', 'updated_at')

    def create(self, validated_data):
        events = None
        meta = None
        repo = None
        issue = None
        if 'events' in validated_data:
            events = validated_data.pop('events')
        if 'meta' in validated_data:
            meta = validated_data.pop('meta')
        if 'repo' in validated_data:
            repo = validated_data.pop('repo')
        if 'issue' in validated_data:
            issue = validated_data.pop('issue')

        instance = super(IntegrationSerializer, self).create(validated_data)
        self.save_events(instance, events)
        self.save_meta(instance, meta)
        self.save_repo_meta(instance, repo)
        self.save_issue_meta(instance, issue)
        return instance

    def update(self, instance, validated_data):
        events = None
        meta = None
        repo = None
        issue = None
        if 'events' in validated_data:
            events = validated_data.pop('events')
        if 'meta' in validated_data:
            meta = validated_data.pop('meta')
        if 'repo' in validated_data:
            repo = validated_data.pop('repo')
        if 'issue' in validated_data:
            issue = validated_data.pop('issue')

        instance = super(IntegrationSerializer, self).update(instance, validated_data)
        self.save_events(instance, events)
        self.save_meta(instance, meta)
        self.save_repo_meta(instance, repo)
        self.save_issue_meta(instance, issue)
        return instance

    def save_events(self, instance, events):
        if events:
            instance.events.clear()
            for item in events:
                try:
                    instance.events.add(item)
                except:
                    pass

    def save_meta(self, instance, meta):
        if meta:
            for item in meta:
                defaults = {'created_by': self.get_current_user() or instance.user}
                defaults.update(item)
                try:
                    IntegrationMeta.objects.update_or_create(
                        integration=instance, meta_key=item['meta_key'], defaults=defaults
                    )
                except:
                    pass

    def save_repo_meta(self, instance, repo):
        if repo:
            for key, value in repo.iteritems():
                defaults = {
                    'created_by': self.get_current_user() or instance.user,
                    'meta_key': 'repo_%s' % key,
                    'meta_value': value
                }
                try:
                    IntegrationMeta.objects.update_or_create(
                        integration=instance, meta_key=defaults['meta_key'], defaults=defaults
                    )
                except:
                    pass

    def save_issue_meta(self, instance, issue):
        if issue:
            for key, value in issue.iteritems():
                defaults = {
                    'created_by': self.get_current_user() or instance.user,
                    'meta_key': 'issue_%s' % key,
                    'meta_value': value
                }
                try:
                    IntegrationMeta.objects.update_or_create(
                        integration=instance, meta_key=defaults['meta_key'], defaults=defaults
                    )
                except:
                    pass


class SimpleIntegrationActivitySerializer(ContentTypeAnnotatedModelSerializer):
    integration = SimpleIntegrationSerializer()
    user_display_name = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()

    class Meta:
        model = IntegrationActivity

    def get_user_display_name(self, obj):
        return obj.fullname or obj.username

    def get_summary(self, obj):
        event_name = obj.event.id
        if event_name == slugs.EVENT_PUSH:
            return 'pushed new code'
        elif event_name in [slugs.EVENT_BRANCH, slugs.EVENT_TAG, slugs.EVENT_PULL_REQUEST, slugs.EVENT_ISSUE, slugs.EVENT_RELEASE, slugs.EVENT_WIKI]:
            msg_map = {
                slugs.EVENT_BRANCH: 'a branch',
                slugs.EVENT_TAG: 'a tag',
                slugs.EVENT_PULL_REQUEST: 'a pull request',
                slugs.EVENT_ISSUE: 'an issue',
                slugs.EVENT_RELEASE: 'a release',
                slugs.EVENT_WIKI: 'a wiki'
            }
            return '%s %s' % (obj.action, msg_map[event_name])
        elif event_name in [slugs.EVENT_COMMIT_COMMENT, slugs.EVENT_ISSUE_COMMENT, slugs.EVENT_PULL_REQUEST_COMMENT]:
            msg_map = {
                slugs.EVENT_COMMIT_COMMENT: 'a commit',
                slugs.EVENT_ISSUE_COMMENT: 'an issue',
                slugs.EVENT_PULL_REQUEST_COMMENT: 'a pull request'
            }
            return 'commented on %s' % msg_map[event_name]
        return None
