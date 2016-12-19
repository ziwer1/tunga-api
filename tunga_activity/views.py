from actstream.models import Action
from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser

from tunga_activity.filters import ActionFilter
from tunga_activity.serializers import ActivitySerializer


class ActionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Activity Resource
    """
    queryset = Action.objects.all()
    serializer_class = ActivitySerializer
    permission_classes = [IsAdminUser]
    filter_class = ActionFilter
    search_fields = (
        'comments__body', 'messages__body', 'uploads__file', 'messages__attachments__file', 'comments__uploads__file'
    )
