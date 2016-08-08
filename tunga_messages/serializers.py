from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from tunga_messages.filterbackends import new_messages_filter
from tunga_messages.models import Message, Attachment, Channel, ChannelUser
from tunga_messages.tasks import get_or_create_direct_channel
from tunga_utils.mixins import GetCurrentUserAnnotatedSerializerMixin
from tunga_utils.models import Upload
from tunga_utils.serializers import CreateOnlyCurrentUserDefault, SimpleUploadSerializer, \
    SimpleUserSerializer, DetailAnnotatedModelSerializer, ContentTypeAnnotatedModelSerializer, UploadSerializer


class SimpleChannelSerializer(serializers.ModelSerializer):
    created_by = SimpleUserSerializer()

    class Meta:
        model = Channel
        exclude = ('participants',)


class DirectChannelSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(required=True, queryset=get_user_model().objects.all())


class ChannelLastReadSerializer(serializers.Serializer):
    last_read = serializers.IntegerField(required=True)


class ChannelDetailsSerializer(serializers.ModelSerializer):
    created_by = SimpleUserSerializer()
    participants = SimpleUserSerializer(many=True)

    class Meta:
        model = Channel
        fields = ('created_by', 'participants')


class ChannelSerializer(DetailAnnotatedModelSerializer, GetCurrentUserAnnotatedSerializerMixin):
    created_by = SimpleUserSerializer(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())
    display_type = serializers.CharField(required=False, read_only=True, source='get_type_display')
    participants = serializers.PrimaryKeyRelatedField(
        required=True, many=True, queryset=get_user_model().objects.all()
    )
    attachments = UploadSerializer(read_only=True, required=False, many=True, source='all_attachments')
    user = serializers.SerializerMethodField(read_only=True, required=False)
    new = serializers.SerializerMethodField(read_only=True, required=False)
    last_read = serializers.SerializerMethodField(read_only=True, required=False)

    class Meta:
        model = Channel
        read_only_fields = ('created_at', 'type')
        details_serializer = ChannelDetailsSerializer

    def validate_participants(self, value):
        if not isinstance(value, list) or not value:
            raise ValidationError('Select some participants for this conversation')
        return value

    def create(self, validated_data):
        participants = None
        if 'participants' in validated_data:
            participants = validated_data.pop('participants')
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
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        self.save_participants(instance, participants)
        return instance

    def save_participants(self, instance, participants):
        if participants:
            participants.append(instance.created_by)
            for user in participants:
                try:
                    ChannelUser.objects.update_or_create(channel=instance, user=user)
                except:
                    pass

    def get_user(self, obj):
        user = self.get_current_user()
        if user:
            if obj.participants.count() == 2:
                for participant in obj.participants.all():
                    if participant.id != user.id:
                        return SimpleUserSerializer(participant).data
        return None

    def get_new(self, obj):
        user = self.get_current_user()
        if user:
            return new_messages_filter(queryset=obj.target_actions.filter(channels__channeluser__user=user), user=user).count()
        return 0

    def get_last_read(self, obj):
        user = self.get_current_user()
        if user:
            try:
                return obj.channeluser_set.get(user=user).last_read
            except:
                pass
        return 0


class MessageSerializer(serializers.ModelSerializer, GetCurrentUserAnnotatedSerializerMixin):
    user = SimpleUserSerializer(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())
    excerpt = serializers.CharField(required=False, read_only=True)
    attachments = UploadSerializer(read_only=True, required=False, many=True)

    class Meta:
        model = Message
        read_only_fields = ('created_at',)


class ChannelUserSerializer(ContentTypeAnnotatedModelSerializer):
    channel = SimpleChannelSerializer()
    user = SimpleUserSerializer()

    class Meta:
        model = ChannelUser


