from django.contrib.auth import get_user_model
from django.db.models.query_utils import Q
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from tunga_messages.utils import channel_activity_new_messages_filter
from tunga_messages.models import Message, Channel, ChannelUser
from tunga_messages.tasks import get_or_create_direct_channel
from tunga_utils.constants import CHANNEL_TYPE_SUPPORT, CHANNEL_TYPE_DEVELOPER
from tunga_utils.mixins import GetCurrentUserAnnotatedSerializerMixin
from tunga_utils.serializers import CreateOnlyCurrentUserDefault, SimpleUserSerializer, DetailAnnotatedModelSerializer, ContentTypeAnnotatedModelSerializer, UploadSerializer


class SimpleChannelSerializer(serializers.ModelSerializer):
    created_by = SimpleUserSerializer()

    class Meta:
        model = Channel
        exclude = ('participants',)


class DirectChannelSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(required=True, queryset=get_user_model().objects.all())


class SupportChannelSerializer(serializers.Serializer, GetCurrentUserAnnotatedSerializerMixin):
    id = serializers.IntegerField(required=False, allow_null=True)
    name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    subject = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_name(self, value):
        current_user = self.get_current_user()
        if current_user and current_user.is_authenticated():
            return value
        if not value:
            raise ValidationError('Please enter your name')
        return value

    def validate_email(self, value):
        current_user = self.get_current_user()
        if current_user and current_user.is_authenticated():
            return value
        if not value:
            raise ValidationError('Please enter your email')
        return value


class DeveloperChannelSerializer(serializers.Serializer, GetCurrentUserAnnotatedSerializerMixin):
    subject = serializers.CharField(required=True)
    message = serializers.CharField(required=True)


class ChannelDetailsSerializer(serializers.ModelSerializer):
    participants = SimpleUserSerializer(many=True)

    class Meta:
        model = Channel
        fields = ('participants',)


class ChannelSerializer(DetailAnnotatedModelSerializer, GetCurrentUserAnnotatedSerializerMixin):
    created_by = SimpleUserSerializer(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())
    display_type = serializers.CharField(required=False, read_only=True, source='get_type_display')
    participants = serializers.PrimaryKeyRelatedField(
        required=True, many=True, queryset=get_user_model().objects.all()
    )
    attachments = UploadSerializer(read_only=True, required=False, many=True, source='all_attachments')
    user = serializers.SerializerMethodField(read_only=True, required=False)
    new_messages = serializers.IntegerField(read_only=True, required=False)
    new = serializers.SerializerMethodField(read_only=True, required=False)
    last_read = serializers.SerializerMethodField(read_only=True, required=False)
    alt_subject = serializers.CharField(required=False, read_only=True, source='get_alt_subject')

    class Meta:
        model = Channel
        exclude = ()
        read_only_fields = ('created_at', 'type')
        details_serializer = ChannelDetailsSerializer

    def validate_participants(self, value):
        error = 'Select some participants for this conversation'
        if not isinstance(value, list) or not value:
            raise ValidationError(error)
        participants = self.clean_participants(value)
        if not participants:
            raise ValidationError(error)
        return value

    def create(self, validated_data):
        participants = None
        if 'participants' in validated_data:
            participants = validated_data.pop('participants')
        participants = self.clean_participants(participants)
        subject = validated_data.get('subject', None)
        if not subject and isinstance(participants, list) and len(participants) == 1:
            # Create or get a direct channel
            # if only one other participant is given and no subject is stated for the communication
            current_user = self.get_current_user()
            channel = get_or_create_direct_channel(current_user, participants[0])
        else:
            if not subject:
                raise ValidationError({'subject': 'Enter a subject for this conversation'})
            channel = Channel.objects.create(**validated_data)
        self.save_participants(channel, participants)
        return channel

    def update(self, instance, validated_data):
        participants = None
        if 'participants' in validated_data:
            participants = validated_data.pop('participants')
        participants = self.clean_participants(participants)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        subject = validated_data.get('subject', None)
        if not subject and isinstance(participants, list) and len(participants) > 1:
            raise ValidationError({'subject': 'Enter a subject for this conversation'})
        instance.save()
        self.save_participants(instance, participants)
        return instance

    def clean_participants(self, participants):
        current_user = self.get_current_user()
        if isinstance(participants, (list, tuple)) and current_user:
            return [user_id for user_id in participants if user_id != current_user.id]
        return participants

    def save_participants(self, instance, participants):
        if participants:
            participants.append(instance.created_by)
            for user in participants:
                try:
                    ChannelUser.objects.update_or_create(channel=instance, user=user)
                except:
                    pass

    def get_user(self, obj):
        current_user = self.get_current_user()
        if current_user:
            receiver = obj.get_receiver(current_user)
            if receiver:
                return SimpleUserSerializer(receiver).data
        return None

    def get_new(self, obj):
        user = self.get_current_user()
        if user:
            return channel_activity_new_messages_filter(
                queryset=obj.target_actions.filter(channels__channeluser__user=user), user=user
            ).count()
        return 0

    def get_last_read(self, obj):
        user = self.get_current_user()
        if user:
            try:
                return obj.channeluser_set.get(user=user).last_read
            except:
                pass
        else:
            return obj.last_read
        return 0


class SenderSerializer(serializers.Serializer):
    id = serializers.CharField(required=False)
    username = serializers.CharField(required=False)
    name = serializers.CharField(required=False)
    display_name = serializers.CharField(required=False)
    short_name = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    avatar_url = serializers.URLField(required=False)
    inquirer = serializers.BooleanField(required=False)


class MessageSerializer(serializers.ModelSerializer, GetCurrentUserAnnotatedSerializerMixin):
    user = SimpleUserSerializer(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())
    excerpt = serializers.CharField(required=False, read_only=True)
    attachments = UploadSerializer(read_only=True, required=False, many=True)
    sender = SenderSerializer(read_only=True, required=False)
    html_body = serializers.CharField(required=False, read_only=True)

    class Meta:
        model = Message
        exclude = ('alt_user', 'source', 'extra')
        read_only_fields = ('created_at',)


class ChannelUserSerializer(ContentTypeAnnotatedModelSerializer):
    channel = SimpleChannelSerializer()
    user = SimpleUserSerializer()

    class Meta:
        model = ChannelUser
        fields = '__all__'


