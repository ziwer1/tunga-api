from django.contrib.contenttypes.models import ContentType
from dry_rest_permissions.generics import DRYObjectPermissions
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from tunga_comments.filters import CommentFilter
from tunga_comments.models import Comment
from tunga_comments.serializers import CommentSerializer
from tunga_utils.models import Upload


class CommentViewSet(viewsets.ModelViewSet):
    """
    Comment Resource
    """
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated, DRYObjectPermissions]
    filter_class = CommentFilter
    search_fields = ('user__username', )

    def perform_create(self, serializer):
        comment = serializer.save()
        uploads = self.request.FILES
        content_type = ContentType.objects.get_for_model(Comment)
        if uploads:
            for file in uploads.itervalues():
                upload = Upload(object_id=comment.id, content_type=content_type, file=file, user=self.request.user)
                upload.save()
