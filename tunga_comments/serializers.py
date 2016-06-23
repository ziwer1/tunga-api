from rest_framework import serializers

from tunga_comments.models import Comment
from tunga_utils.serializers import CreateOnlyCurrentUserDefault, UploadSerializer, SimpleUserSerializer


class CommentSerializer(serializers.ModelSerializer):
    user = SimpleUserSerializer(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())
    uploads = UploadSerializer(read_only=True, required=False, many=True)

    class Meta:
        model = Comment
        read_only_fields = ('created_at',)

