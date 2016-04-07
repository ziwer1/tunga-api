from django.contrib.auth import get_user_model
from rest_framework import serializers

from tunga_auth.serializers import SimpleUserSerializer
from tunga_tasks.models import Task, Application, Participation, TaskRequest, SavedTask
from tunga_utils.serializers import ContentTypeAnnotatedSerializer, DetailAnnotatedSerializer, SkillSerializer, \
    CreateOnlyCurrentUserDefault


class SimpleTaskSerializer(ContentTypeAnnotatedSerializer):
    user = SimpleUserSerializer()

    class Meta:
        model = Task
        fields = ('id', 'user', 'title', 'currency', 'fee')


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
    assignee = SimpleUserSerializer()
    applications = SimpleApplicationSerializer(many=True, source='application_set')
    participation = SimpleParticipationSerializer(many=True, source='participation_set')

    class Meta:
        model = Task
        fields = ('user', 'skills', 'visible_to', 'assignee', 'applications', 'participation')


class TaskSerializer(SimpleTaskSerializer, DetailAnnotatedSerializer):
    user = serializers.PrimaryKeyRelatedField(required=False, read_only=True, default=CreateOnlyCurrentUserDefault)
    skills = serializers.CharField()
    visible_to = serializers.PrimaryKeyRelatedField(many=True, queryset=get_user_model().objects.all())

    class Meta:
        model = Task
        exclude = ('applicants', 'participants')
        read_only_fields = ('created_at',)
        details_serializer = TaskDetailsSerializer


class ApplicationDetailsSerializer(SimpleApplicationSerializer):
    task = SimpleTaskSerializer()

    class Meta:
        model = Application
        fields = ('user', 'task')


class ApplicationSerializer(ContentTypeAnnotatedSerializer, DetailAnnotatedSerializer):
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
    created_by = serializers.PrimaryKeyRelatedField(required=False, read_only=True, default=CreateOnlyCurrentUserDefault)

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
    user = serializers.PrimaryKeyRelatedField(required=False, read_only=True, default=CreateOnlyCurrentUserDefault)

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
    user = serializers.PrimaryKeyRelatedField(required=False, read_only=True, default=CreateOnlyCurrentUserDefault)

    class Meta:
        model = SavedTask
        exclude = ('created_at',)
        details_serializer = SavedTaskDetailsSerializer
