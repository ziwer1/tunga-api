from django.contrib.auth import get_user_model
from django.db.models.query_utils import Q
from rest_framework import serializers

from tunga_auth.serializers import SimpleUserSerializer, UserSerializer
from tunga_tasks.emails import send_new_task_email
from tunga_tasks.models import Task, Application, Participation, TaskRequest, SavedTask
from tunga_utils.serializers import ContentTypeAnnotatedSerializer, DetailAnnotatedSerializer, SkillSerializer, \
    CreateOnlyCurrentUserDefault


class SimpleTaskSerializer(ContentTypeAnnotatedSerializer):
    user = SimpleUserSerializer()

    class Meta:
        model = Task
        fields = ('id', 'user', 'title', 'currency', 'fee', 'closed', 'paid', 'display_fee')


class SimpleApplicationSerializer(ContentTypeAnnotatedSerializer):
    user = SimpleUserSerializer()

    class Meta:
        model = Application
        exclude = ('created_at',)


class SimpleParticipationSerializer(ContentTypeAnnotatedSerializer):
    user = SimpleUserSerializer()

    class Meta:
        model = Participation
        exclude = ('created_at',)


class TaskDetailsSerializer(ContentTypeAnnotatedSerializer):
    user = SimpleUserSerializer()
    skills = SkillSerializer(many=True)
    visible_to = SimpleUserSerializer(many=True)
    assignee = serializers.SerializerMethodField(required=False, read_only=True)
    applications = SimpleApplicationSerializer(many=True, source='application_set')
    participation = SimpleParticipationSerializer(many=True, source='participation_set')

    class Meta:
        model = Task
        fields = ('user', 'skills', 'visible_to', 'assignee', 'applications', 'participation')

    def get_assignee(self, obj):
        try:
            assignee = obj.participation_set.get((Q(accepted=True) | Q(responded=False)), assignee=True)
            return {
                'user': SimpleUserSerializer(assignee.user).data,
                'accepted': assignee.accepted,
                'responded': assignee.responded
            }
        except:
            return None


class TaskSerializer(ContentTypeAnnotatedSerializer, DetailAnnotatedSerializer):
    user = serializers.PrimaryKeyRelatedField(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())
    display_fee = serializers.CharField(required=False, read_only=True)
    skills = serializers.CharField(required=True, allow_blank=True, allow_null=True)
    visible_to = serializers.PrimaryKeyRelatedField(many=True, queryset=get_user_model().objects.all(), required=False)
    deadline = serializers.DateTimeField(required=False, allow_null=True)
    can_apply = serializers.SerializerMethodField(read_only=True, required=False)
    can_save = serializers.SerializerMethodField(read_only=True, required=False)
    is_participant = serializers.SerializerMethodField(read_only=True, required=False)
    my_participation = serializers.SerializerMethodField(read_only=True, required=False)
    summary = serializers.CharField(read_only=True, required=False)
    assignee = serializers.SerializerMethodField(required=False, read_only=True)
    participants = serializers.PrimaryKeyRelatedField(many=True, queryset=get_user_model().objects.all(), required=False, write_only=True)

    class Meta:
        model = Task
        exclude = ('applicants',)
        read_only_fields = ('created_at',)
        details_serializer = TaskDetailsSerializer

    def create(self, validated_data):
        skills = None
        participants = None
        if 'skills' in validated_data:
            skills = validated_data.pop('skills')
        if 'participants' in validated_data:
            participants = validated_data.pop('participants')
        instance = super(TaskSerializer, self).create(validated_data)
        self.save_skills(instance, skills)
        self.save_participants(instance, participants)

        # Triggered here instead of in the post_save signal to allow skills to be attached first
        # TODO: Consider moving this trigger
        send_new_task_email(instance)
        return instance

    def update(self, instance, validated_data):
        skills = None
        participants = None
        if 'skills' in validated_data:
            skills = validated_data.pop('skills')
        if 'participants' in validated_data:
            participants = validated_data.pop('participants')
        instance = super(TaskSerializer, self).update(instance, validated_data)
        self.save_skills(instance, skills)
        self.save_participants(instance, participants)
        return instance

    def save_skills(self, task, skills):
        if skills is not None:
            task.skills = skills
            task.save()

    def save_participants(self, task, participants):
        if participants:
            assignee = self.initial_data.get('assignee', None)
            confirmed_participants = self.initial_data.get('confirmed_participants', None)
            rejected_participants = self.initial_data.get('rejected_participants', None)
            created_by = task.user
            request = self.context.get("request", None)
            if request:
                user = getattr(request, "user", None)
                if user:
                    created_by = user

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

                    Participation.objects.update_or_create(task=task, user=user, defaults=defaults)
                    if user.id == assignee:
                        changed_assignee = True
                except:
                    pass
            if assignee and changed_assignee:
                Participation.objects.exclude(user__id=assignee).filter(task=task).update(assignee=False)

    def get_can_apply(self, obj):
        if obj.closed:
            return False
        request = self.context.get("request", None)
        if request:
            user = getattr(request, "user", None)
            if user:
                if obj.user == user:
                    return False
                return obj.applicants.filter(id=user.id).count() == 0 and \
                       obj.participation_set.filter(user=user).count() == 0
        return False

    def get_can_save(self, obj):
        request = self.context.get("request", None)
        if request:
            user = getattr(request, "user", None)
            if user:
                if obj.user == user:
                    return False
                return obj.savedtask_set.filter(user=user).count() == 0
        return False

    def get_is_participant(self, obj):
        request = self.context.get("request", None)
        if request:
            user = getattr(request, "user", None)
            if user:
                return obj.participation_set.filter((Q(accepted=True) | Q(responded=False)), user=user).count() == 1
        return False

    def get_my_participation(self, obj):
        request = self.context.get("request", None)
        if request:
            user = getattr(request, "user", None)
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

    def get_assignee(self, obj):
        try:
            assignee = obj.participation_set.get((Q(accepted=True) | Q(responded=False)), assignee=True)
            return {
                'user': assignee.user.id,
                'accepted': assignee.accepted,
                'responded': assignee.responded
            }
        except:
            return None


class ApplicationDetailsSerializer(SimpleApplicationSerializer):
    user = UserSerializer()
    task = SimpleTaskSerializer()

    class Meta:
        model = Application
        fields = ('user', 'task')


class ApplicationSerializer(ContentTypeAnnotatedSerializer, DetailAnnotatedSerializer):
    user = serializers.PrimaryKeyRelatedField(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())

    class Meta:
        model = Application
        exclude = ('created_at',)
        details_serializer = ApplicationDetailsSerializer


class ParticipationDetailsSerializer(SimpleParticipationSerializer):
    created_by = SimpleUserSerializer()
    task = SimpleTaskSerializer()

    class Meta:
        model = Participation
        fields = ('user', 'task', 'created_by')


class ParticipationSerializer(ContentTypeAnnotatedSerializer, DetailAnnotatedSerializer):
    created_by = serializers.PrimaryKeyRelatedField(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())

    class Meta:
        model = Participation
        exclude = ('created_at',)
        details_serializer = ParticipationDetailsSerializer


class TaskRequestDetailsSerializer(serializers.ModelSerializer):
    user = SimpleUserSerializer()
    task = SimpleTaskSerializer()

    class Meta:
        model = TaskRequest
        fields = ('user', 'task')


class TaskRequestSerializer(ContentTypeAnnotatedSerializer, DetailAnnotatedSerializer):
    user = serializers.PrimaryKeyRelatedField(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())

    class Meta:
        model = TaskRequest
        exclude = ('created_at',)
        details_serializer = TaskRequestDetailsSerializer


class SavedTaskDetailsSerializer(serializers.ModelSerializer):
    user = SimpleUserSerializer()
    task = SimpleTaskSerializer()

    class Meta:
        model = SavedTask
        fields = ('user', 'task')


class SavedTaskSerializer(ContentTypeAnnotatedSerializer, DetailAnnotatedSerializer):
    user = serializers.PrimaryKeyRelatedField(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())

    class Meta:
        model = SavedTask
        exclude = ('created_at',)
        details_serializer = SavedTaskDetailsSerializer
