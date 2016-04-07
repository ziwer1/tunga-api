from dry_rest_permissions.generics import DRYObjectPermissions
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from tunga_comments.filters import CommentFilter
from tunga_comments.models import Comment
from tunga_comments.serializers import CommentSerializer


class CommentViewSet(viewsets.ModelViewSet):
    """
    Manage Comments
    """
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated, DRYObjectPermissions]
    filter_class = CommentFilter
    search_fields = ('user__username', )
