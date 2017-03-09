import datetime
from decimal import Decimal

from allauth.account.signals import user_signed_up
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MinValueValidator
from django.db.models.query_utils import Q
from django.template.defaultfilters import floatformat
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from tunga.settings import TUNGA_SHARE_PERCENTAGE
from tunga_auth.serializers import UserSerializer
from tunga_profiles.utils import profile_check
from tunga_tasks import slugs
from tunga_tasks.models import Task, Application, Participation, TaskRequest, TimeEntry, ProgressEvent, ProgressReport, \
    Project, IntegrationMeta, Integration, IntegrationEvent, IntegrationActivity, TASK_PAYMENT_METHOD_CHOICES, \
    TaskInvoice
from tunga_tasks.notifications import notify_new_task
from tunga_tasks.signals import application_response, participation_response, task_applications_closed, task_closed, \
    task_integration
from tunga_utils.constants import PROGRESS_EVENT_TYPE_MILESTONE, USER_TYPE_PROJECT_OWNER, USER_SOURCE_TASK_WIZARD, \
    TASK_SCOPE_ONGOING, VISIBILITY_CUSTOM, TASK_SCOPE_TASK, TASK_SCOPE_PROJECT, TASK_SOURCE_NEW_USER
from tunga_utils.helpers import clean_meta_value
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
        fields = (
            'id', 'user', 'title', 'currency', 'fee', 'closed', 'paid', 'display_fee',
            'type', 'scope', 'is_project', 'is_task'
        )


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


class TaskPaymentSerializer(serializers.Serializer):
    user = InvoiceUserSerializer(required=False, read_only=True)
    payment_method = serializers.ChoiceField(choices=TASK_PAYMENT_METHOD_CHOICES, required=True)
    fee = serializers.DecimalField(max_digits=19, decimal_places=4)


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
            try:
                participation = obj.task.participation_set.get(user=current_user)
                share = obj.task.get_user_participation_share(participation.id)
                return obj.get_amount_details(share=share)
            except:
                pass
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
    parent = SimpleTaskSerializer()
    skills = SkillSerializer(many=True)
    applications = SimpleApplicationSerializer(many=True, source='application_set')
    participation = SimpleParticipationSerializer(many=True, source='participation_set')
    participation_shares = ParticipantShareSerializer(many=True, source='get_participation_shares')

    class Meta:
        model = Task
        fields = ('project', 'is_project', 'parent', 'amount', 'skills', 'applications', 'participation', 'participation_shares')


class TaskSerializer(ContentTypeAnnotatedModelSerializer, DetailAnnotatedModelSerializer,
                     GetCurrentUserAnnotatedSerializerMixin):
    user = SimpleUserSerializer(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())
    display_fee = serializers.SerializerMethodField(required=False, read_only=True)
    amount = serializers.JSONField(required=False, read_only=True)
    is_payable = serializers.BooleanField(required=False, read_only=True)
    is_project = serializers.BooleanField(required=False, read_only=True)
    is_task = serializers.BooleanField(required=False, read_only=True)
    excerpt = serializers.CharField(required=False, read_only=True)
    skills = serializers.CharField(
        required=False, error_messages={'blank': 'Please specify the skills required for this task'}
    )
    payment_status = serializers.CharField(required=False, read_only=True)
    deadline = serializers.DateTimeField(required=False, allow_null=True)
    can_apply = serializers.SerializerMethodField(read_only=True, required=False)
    can_save = serializers.SerializerMethodField(read_only=True, required=False)
    is_participant = serializers.SerializerMethodField(read_only=True, required=False)
    is_admin = serializers.SerializerMethodField(read_only=True, required=False)
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
        extra_kwargs = {
            'type': {'required': True, 'allow_blank': False, 'allow_null': False},
            'scope': {'required': True, 'allow_blank': False, 'allow_null': False}
        }
        details_serializer = TaskDetailsSerializer

    def validate(self, attrs):
        has_parent = attrs.get('parent', None) or (self.instance and self.instance.parent)
        scope = attrs.get('scope', None) or (self.instance and self.instance.scope)
        is_project = attrs.get('is_project', None) or (self.instance and self.instance.is_project)
        has_requirements = attrs.get('is_project', None) or (self.instance and self.instance.has_requirements)
        coders_needed = attrs.get('coders_needed', None)
        pm_required = attrs.get('pm_required', None)

        fee = attrs.get('fee', None)
        title = attrs.get('title', None)
        skills = attrs.get('skills', None)
        visibility = attrs.get('visibility', None)

        description = attrs.get('description', None)
        email = self.initial_data.get('email', None)
        first_name = self.initial_data.get('first_name', None)
        last_name = self.initial_data.get('last_name', None)

        current_user = self.get_current_user()

        errors = dict()

        if current_user and current_user.is_authenticated():
            if scope == TASK_SCOPE_TASK or has_parent:
                if not has_parent and fee:
                    MinValueValidator(15, message='Minimum pledge amount is EUR 15')(fee)
                if not title and not self.partial:
                    errors.update({'title': 'This field is required.'})
                if not description and not self.partial:
                    errors.update({'description': 'This field is required.'})
                if not skills and not self.partial:
                    errors.update({'skills': 'This field is required.'})
                if visibility == VISIBILITY_CUSTOM and not (
                            attrs.get('participation', None) or attrs.get('participants', None)
                ):
                    errors.update({'visibility': 'Please choose at least one developer for this task'})
            if scope == TASK_SCOPE_ONGOING:
                if not skills and not self.partial:
                    errors.update({'skills': 'This field is required.'})
                if not coders_needed and not self.partial:
                    errors.update({'coders_needed': 'This field is required.'})
            if scope == TASK_SCOPE_PROJECT:
                if not title and not self.partial:
                    errors.update({'title': 'This field is required.'})
                if not skills and not self.partial:
                    errors.update({'skills': 'This field is required.'})
                if not pm_required and not self.partial:
                    errors.update({'pm_required': 'This field is required.'})
        else:
            if email:
                try:
                    get_user_model().objects.get(email=email)
                    errors.update({
                        'form': 'Looks like you already have a Tunga account. Please login to create new tasks.',
                        'email': 'This email address is already attached to an account on Tunga'
                    })
                except get_user_model().DoesNotExist:
                    pass
            else:
                errors.update({'email': 'This field is required.'})
            if not first_name:
                errors.update({'first_name': 'This field is required.'})
            if not last_name:
                errors.update({'last_name': 'This field is required.'})

        if errors:
            raise ValidationError(errors)

        return attrs

    def save_task(self, validated_data, instance=None):
        current_user = self.get_current_user()
        if current_user and current_user.is_authenticated() and not instance and not profile_check(current_user):
            ValidationError('You need complete your profile before you can post tasks')

        if instance and 'fee' in validated_data and validated_data['fee'] < instance.fee:
            raise ValidationError({
                'fee': 'You cannot reduce the fee for the task, Please contact support@tunga.io for assistance'
            })

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

        initial_apply = True
        initial_closed = False
        new_user = None
        is_update = bool(instance)

        if instance:
            initial_apply = instance.apply
            initial_closed = instance.closed

            if not instance.closed and validated_data.get('closed'):
                validated_data['closed_at'] = datetime.datetime.utcnow()

            if not instance.paid and validated_data.get('paid'):
                validated_data['paid_at'] = datetime.datetime.utcnow()
            instance = super(TaskSerializer, self).update(instance, validated_data)
        else:
            if not current_user or not current_user.is_authenticated():
                validated_data['source'] = TASK_SOURCE_NEW_USER
            if participation or participants:
                # Close applications if paticipants are provided when creating task
                validated_data['apply'] = False
                validated_data['apply_closed_at'] = datetime.datetime.utcnow()

            if not current_user or not current_user.is_authenticated():
                # Create user and add them as the creator or task, indicate if task was unauthenticated
                email = self.initial_data.get('email', None)
                first_name = self.initial_data.get('first_name', None)
                last_name = self.initial_data.get('last_name', None)

                new_user = get_user_model().objects.create_user(
                    username=email, email=email, password=get_user_model().objects.make_random_password(),
                    first_name=first_name, last_name=last_name,
                    type=USER_TYPE_PROJECT_OWNER, source=USER_SOURCE_TASK_WIZARD
                )
                if new_user:
                    validated_data.update({'user': new_user})
                    user_signed_up.send(sender=get_user_model(), request=None, user=new_user)

            instance = super(TaskSerializer, self).create(validated_data)

        self.save_skills(instance, skills)
        self.save_participants(instance, participants)
        self.save_participation(instance, participation)
        self.save_milestones(instance, milestones)
        self.save_ratings(instance, ratings)

        if is_update:
            if initial_apply and not instance.apply:
                task_applications_closed.send(sender=Task, task=instance)

            if not initial_closed and instance.closed:
                task_closed.send(sender=Task, task=instance)
        else:
            # Triggered here instead of in the post_save signal to allow skills to be attached first
            # TODO: Consider moving this trigger
            notify_new_task.delay(instance.id, new_user=bool(new_user))
        return instance

    def create(self, validated_data):
        return self.save_task(validated_data)

    def update(self, instance, validated_data):
        return self.save_task(validated_data, instance=instance)

    def save_skills(self, task, skills):
        if skills is not None:
            task.skills = skills
            task.save()

    def save_participation(self, task, participation):
        if participation:
            new_assignee = None
            for item in participation:
                if 'accepted' in item and item.get('accepted', False):
                    item['activated_at'] = datetime.datetime.utcnow()
                defaults = item
                if isinstance(defaults, dict):
                    current_user = self.get_current_user()
                    participation_creator = task.user
                    if current_user and current_user.is_authenticated() and current_user != item.get('user', None):
                        participation_creator = current_user
                    defaults['created_by'] = participation_creator

                try:
                    participation_obj, created = Participation.objects.update_or_create(
                        task=task, user=item['user'], defaults=defaults)
                    if (not created) and 'accepted' in item:
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
            created_by = self.get_current_user() or task.user

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
                    if (not created) and (user.id in rejected_participants or user.id in confirmed_participants):
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
        if not obj.fee:
            return None
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
        return False

    def get_is_participant(self, obj):
        user = self.get_current_user()
        if user:
            return obj.subtask_participants_inclusive_filter.filter((Q(accepted=True) | Q(responded=False)), user=user).count() > 0
        return False

    def get_is_admin(self, obj):
        user = self.get_current_user()
        return obj.has_admin_access(user)

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
            'hours_needed': {'required': True, 'allow_null': False},
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


class TimeEntryDetailsSerializer(serializers.ModelSerializer):
    user = SimpleUserSerializer()
    task = SimpleTaskSerializer()

    class Meta:
        model = TimeEntry
        fields = ('user', 'task')


class TimeEntrySerializer(ContentTypeAnnotatedModelSerializer, DetailAnnotatedModelSerializer):
    user = SimpleUserSerializer(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())

    class Meta:
        model = TimeEntry
        read_only_fields = ('created_at', 'updated_at')
        details_serializer = TimeEntryDetailsSerializer


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
        model = ProgressReport
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

    # Write Only
    repo = serializers.JSONField(required=False, write_only=True, allow_null=True)
    issue = serializers.JSONField(required=False, write_only=True, allow_null=True)
    project = serializers.JSONField(required=False, write_only=True, allow_null=True)
    team = serializers.JSONField(required=False, write_only=True, allow_null=True)
    channel = serializers.JSONField(required=False, write_only=True, allow_null=True)

    # Read Only
    repo_id = serializers.CharField(required=False, read_only=True)
    issue_id = serializers.CharField(required=False, read_only=True)
    project_id = serializers.CharField(required=False, read_only=True)
    project_task_id = serializers.CharField(required=False, read_only=True)
    team_id = serializers.CharField(required=False, read_only=True)
    team_name = serializers.CharField(required=False, read_only=True)
    channel_id = serializers.CharField(required=False, read_only=True)
    channel_name = serializers.CharField(required=False, read_only=True)

    class Meta:
        model = Integration
        exclude = ('secret',)
        read_only_fields = ('created_at', 'updated_at')

    def send_creation_signal(self, instance):
        task_integration.send(sender=Integration, integration=instance)

    def save_integration(self, validated_data, instance=None):
        events = None
        if 'events' in validated_data:
            events = validated_data.pop('events')
        meta = None
        if 'meta' in validated_data:
            meta = validated_data.pop('meta')
        metadata_objects = dict()
        metadata_keys = ['repo', 'issue', 'project', 'team', 'channel']
        for key in metadata_keys:
            if key in validated_data:
                metadata_objects[key] = validated_data.pop(key)

        if instance:
            instance = super(IntegrationSerializer, self).update(instance, validated_data)
        else:
            instance = super(IntegrationSerializer, self).create(validated_data)
        self.save_events(instance, events)
        self.save_meta(instance, meta)
        for key in metadata_keys:
            self.save_meta_object(instance, metadata_objects.get(key, None), key)

        self.send_creation_signal(instance)
        return instance

    def create(self, validated_data):
        return self.save_integration(validated_data)

    def update(self, instance, validated_data):
        return self.save_integration(validated_data, instance=instance)

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

    def save_meta_object(self, instance, meta_object, prefix):
        if meta_object:
            for key in meta_object:
                defaults = {
                    'created_by': self.get_current_user() or instance.user,
                    'meta_key': '%s_%s' % (prefix, key),
                    'meta_value': clean_meta_value(meta_object[key])
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
