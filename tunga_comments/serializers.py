from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from tunga_auth.serializers import SimpleUserSerializer
from tunga_comments.models import Comment
from tunga_utils.models import Upload
from tunga_utils.serializers import CreateOnlyCurrentUserDefault, UploadSerializer


class CommentSerializer(serializers.ModelSerializer):
    user = SimpleUserSerializer(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())
    uploads = serializers.SerializerMethodField(read_only=True, required=False)

    class Meta:
        model = Comment
        read_only_fields = ('created_at',)

    def get_uploads(self, obj):
        content_type = ContentType.objects.get_for_model(Comment)
        uploads = Upload.objects.filter(content_type=content_type, object_id=obj.id)
        return UploadSerializer(uploads, many=True).data
