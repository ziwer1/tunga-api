from rest_framework import serializers

from tunga_auth.serializers import SimpleUserSerializer
from tunga_comments.models import Comment
from tunga_utils.serializers import CreateOnlyCurrentUserDefault


class CommentSerializer(serializers.ModelSerializer):
    user = SimpleUserSerializer(required=False, read_only=True, default=CreateOnlyCurrentUserDefault)

    class Meta:
        model = Comment
        read_only_fields = ('created_at',)
