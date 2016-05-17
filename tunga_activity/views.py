from actstream.models import Action

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from tunga_activity.filters import ActionFilter
from tunga_activity.serializers import ActionSerializer


class ActionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Activity Resource
    """
    queryset = Action.objects.all()
    serializer_class = ActionSerializer
    permission_classes = [IsAuthenticated]
    filter_class = ActionFilter
