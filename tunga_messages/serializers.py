from django.contrib.auth import get_user_model
from rest_framework import serializers

from tunga_auth.serializers import SimpleUserSerializer
from tunga_messages.models import Message, Reply, Recipient
from tunga_utils.serializers import DetailAnnotatedSerializer, CreateOnlyCurrentUserDefault


class MessageDetailsSerializer(serializers.ModelSerializer):
    user = SimpleUserSerializer()
    recipients = SimpleUserSerializer(many=True)

    class Meta:
        model = Message
        fields = ('user', 'recipients')


class MessageSerializer(DetailAnnotatedSerializer):
    user = serializers.PrimaryKeyRelatedField(required=False, read_only=True, default=CreateOnlyCurrentUserDefault)
    recipients = serializers.PrimaryKeyRelatedField(many=True, queryset=get_user_model().objects.all())

    class Meta:
        model = Message
        read_only_fields = ('created_at',)
        details_serializer = MessageDetailsSerializer

    def create(self, validated_data):
        to_users = validated_data.pop('recipients')
        message = Message.objects.create(**validated_data)
        self.save_recipents(message, to_users)
        return message

    def update(self, instance, validated_data):
        to_users = validated_data.pop('recipients')
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        self.save_recipents(instance, to_users)
        return instance

    def save_recipents(self, message, to_users):
        for user in to_users:
            try:
                Recipient.objects.create(message=message, user=user)
            except:
                pass


class ReplyDetailsSerializer(serializers.ModelSerializer):
    user = SimpleUserSerializer()

    class Meta:
        model = Reply
        fields = ('user',)


class ReplySerializer(DetailAnnotatedSerializer):
    user = serializers.PrimaryKeyRelatedField(required=False, read_only=True, default=CreateOnlyCurrentUserDefault)

    class Meta:
        model = Reply
        read_only_fields = ('created_at',)
        details_serializer = ReplyDetailsSerializer
