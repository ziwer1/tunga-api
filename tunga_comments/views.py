from django.contrib.contenttypes.models import ContentType
from dry_rest_permissions.generics import DRYObjectPermissions
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from tunga_comments.filters import CommentFilter
from tunga_comments.models import Comment
from tunga_comments.serializers import CommentSerializer
from tunga_utils.mixins import SaveUploadsMixin
from tunga_utils.models import Upload


class CommentViewSet(viewsets.ModelViewSet, SaveUploadsMixin):
    """
    Comment Resource
    """
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated, DRYObjectPermissions]
    filter_class = CommentFilter
    search_fields = ('user__username', )
