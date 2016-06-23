from django.contrib.auth import get_user_model
from django.db.models.aggregates import Max
from django.db.models.expressions import F, Value, Case, When
from django.db.models.fields import DateTimeField
from django.db.models.query_utils import Q
from rest_framework import serializers

from tunga_messages.models import Message, Reply, Reception, Attachment
from tunga_utils.mixins import GetCurrentUserAnnotatedSerializerMixin
from tunga_utils.serializers import CreateOnlyCurrentUserDefault, SimpleUploadSerializer, \
    SimpleUserSerializer, DetailAnnotatedModelSerializer


class SimpleAttachmentSerializer(SimpleUploadSerializer):

    class Meta(SimpleUploadSerializer.Meta):
        model = Attachment


class MessageDetailsSerializer(serializers.ModelSerializer):
    user = SimpleUserSerializer()
    recipients = SimpleUserSerializer(many=True)

    class Meta:
        model = Message
        fields = ('user', 'recipients')


class MessageSerializer(DetailAnnotatedModelSerializer, GetCurrentUserAnnotatedSerializerMixin):
    user = serializers.PrimaryKeyRelatedField(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())
    recipients = serializers.PrimaryKeyRelatedField(many=True, queryset=get_user_model().objects.all(),
                                                    allow_null=True, allow_empty=True)
    excerpt = serializers.CharField(required=False, read_only=True)
    is_read = serializers.SerializerMethodField(read_only=True, required=False)
    attachments = SimpleAttachmentSerializer(read_only=True, required=False, many=True)

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
        user = self.get_current_user()
        if user:
            if obj.user == user:
                replies = obj.replies.exclude(user=user)
                if obj.read_at:
                    return replies.filter(created_at__gt=obj.read_at).count() == 0
                return replies.count() == 0
            return obj.reception_set.filter(
                user=user, read_at__isnull=False
            ).annotate(
                latest_created_at=Max(
                    Case(
                        When(
                            ~Q(message__replies__user=user),
                            then='message__replies__created_at'
                        ),
                        default=Value(obj.created_at),
                        output_field=DateTimeField()
                    )
                )
            ).filter(Q(latest_created_at__isnull=True) | Q(read_at__gt=F('latest_created_at')), read_at__gt=obj.created_at).count() >= 1
        return False


class ReplyDetailsSerializer(serializers.ModelSerializer):
    user = SimpleUserSerializer()

    class Meta:
        model = Reply
        fields = ('user',)


class ReplySerializer(DetailAnnotatedModelSerializer):
    user = serializers.PrimaryKeyRelatedField(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())
    excerpt = serializers.CharField(required=False, read_only=True)
    attachments = SimpleAttachmentSerializer(read_only=True, required=False, many=True)

    class Meta:
        model = Reply
        read_only_fields = ('created_at',)
        details_serializer = ReplyDetailsSerializer

