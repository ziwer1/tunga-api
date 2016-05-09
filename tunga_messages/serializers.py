from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db.models.expressions import F
from rest_framework import serializers

from tunga_auth.serializers import SimpleUserSerializer
from tunga_messages.models import Message, Reply, Reception, Attachment
from tunga_utils.serializers import DetailAnnotatedSerializer, CreateOnlyCurrentUserDefault, SimpleUploadSerializer


class SimpleAttachmentSerializer(SimpleUploadSerializer):

    class Meta(SimpleUploadSerializer.Meta):
        model = Attachment


class MessageDetailsSerializer(serializers.ModelSerializer):
    user = SimpleUserSerializer()
    recipients = SimpleUserSerializer(many=True)

    class Meta:
        model = Message
        fields = ('user', 'recipients')


class MessageSerializer(DetailAnnotatedSerializer):
    user = serializers.PrimaryKeyRelatedField(required=False, read_only=True, default=CreateOnlyCurrentUserDefault)
    recipients = serializers.PrimaryKeyRelatedField(many=True, queryset=get_user_model().objects.all(),
                                                    allow_null=True, allow_empty=True)
    is_read = serializers.SerializerMethodField(read_only=True, required=False)
    attachments = serializers.SerializerMethodField(read_only=True, required=False)

    class Meta:
        model = Message
        read_only_fields = ('created_at',)
        details_serializer = MessageDetailsSerializer

    def create(self, validated_data):
        to_users = None
        to_users = validated_data.pop('recipients')
        message = Message.objects.create(**validated_data)
        self.save_recipents(message, to_users)
        return message

    def update(self, instance, validated_data):
        to_users = None
        if 'recipients' in validated_data:
            to_users = validated_data.pop('recipients')
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        self.save_recipents(instance, to_users)
        return instance

    def save_recipents(self, message, to_users):
        if to_users:
            for user in to_users:
                try:
                    Reception.objects.update_or_create(message=message, user=user)
                except:
                    pass

    def get_is_read(self, obj):
        request = self.context.get("request", None)
        if request:
            user = getattr(request, "user", None)
            if user:
                if obj.user == user:
                    if obj.read_at:
                        return obj.replies.filter(message=obj, created_at__gt=obj.read_at).count() == 0
                    return True
                return obj.reception_set.filter(user=user, message=obj, read_at__gt=obj.created_at).count() >= 1
        return False

    def get_attachments(self, obj):
        content_type = ContentType.objects.get_for_model(Message)
        attachments = Attachment.objects.filter(content_type=content_type, object_id=obj.id)
        return SimpleAttachmentSerializer(attachments, many=True).data


class ReplyDetailsSerializer(serializers.ModelSerializer):
    user = SimpleUserSerializer()

    class Meta:
        model = Reply
        fields = ('user',)


class ReplySerializer(DetailAnnotatedSerializer):
    user = serializers.PrimaryKeyRelatedField(required=False, read_only=True, default=CreateOnlyCurrentUserDefault)
    attachments = serializers.SerializerMethodField(read_only=True, required=False)

    class Meta:
        model = Reply
        read_only_fields = ('created_at',)
        details_serializer = ReplyDetailsSerializer

    def get_attachments(self, obj):
        content_type = ContentType.objects.get_for_model(Reply)
        attachments = Attachment.objects.filter(content_type=content_type, object_id=obj.id)
        return SimpleAttachmentSerializer(attachments, many=True).data
