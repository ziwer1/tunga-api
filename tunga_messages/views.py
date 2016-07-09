from django.db.models.aggregates import Max
from django.db.models.expressions import Case, When, F
from django.db.models.fields import DateTimeField
from dry_rest_permissions.generics import DRYObjectPermissions
from rest_framework import viewsets, status
from rest_framework.decorators import detail_route, list_route
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from tunga_messages.filterbackends import MessageFilterBackend, ChannelFilterBackend
from tunga_messages.filters import MessageFilter, ChannelFilter
from tunga_messages.models import Message, Attachment, Channel, ChannelUser
from tunga_messages.serializers import MessageSerializer, ChannelSerializer, DirectChannelSerializer, \
    ChannelLastReadSerializer
from tunga_messages.tasks import get_or_create_direct_channel
from tunga_utils.filterbackends import DEFAULT_FILTER_BACKENDS


class ChannelViewSet(viewsets.ModelViewSet):
    """
    Channel Resource
    """
    queryset = Channel.objects.all().annotate(
        latest_message_created_at=Max('messages__created_at')
    ).annotate(latest_activity_at=Case(
        When(
            latest_message_created_at__isnull=True,
            then='created_at'
        ),
        When(
            latest_message_created_at__gt=F('created_at'),
            then='latest_message_created_at'
        ),
        default='created_at',
        output_field=DateTimeField()
    )).order_by('-latest_activity_at')
    serializer_class = ChannelSerializer
    permission_classes = [IsAuthenticated, DRYObjectPermissions]
    filter_class = ChannelFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (ChannelFilterBackend,)
    search_fields = (
        'subject', 'channeluser__user__username', 'channeluser__user__first_name',
        'channeluser__user__last_name'
    )

    @list_route(
        methods=['post'], url_path='direct',
        permission_classes=[IsAuthenticated], serializer_class=DirectChannelSerializer
    )
    def direct_channel(self, request):
        """
        Gets or creates a direct channel to the user
        ---
        request_serializer: DirectChannelSerializer
        response_serializer: ChannelSerializer
        """
        serializer = self.get_serializer(data=request.data)
        channel = None
        if serializer.is_valid(raise_exception=True):
            user = serializer.validated_data['user']
            channel = get_or_create_direct_channel(request.user, user)
        if not channel:
            return Response(
                {'status': "Couldn't get or create a direct channel"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        response_serializer = ChannelSerializer(channel)
        return Response(response_serializer.data)

    @detail_route(
        methods=['post'], url_path='read',
        permission_classes=[IsAuthenticated], serializer_class=ChannelLastReadSerializer
    )
    def update_read(self, request, pk=None):
        """
        Updates user's read_at for channel
        ---
        request_serializer: ChannelLastReadSerializer
        response_serializer: ChannelSerializer
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        last_read = serializer.validated_data['last_read']
        channel = get_object_or_404(self.get_queryset(), pk=pk)
        if channel.has_object_read_permission(request):
            ChannelUser.objects.update_or_create(user=request.user, channel=channel, defaults={'last_read': last_read})
            response_serializer = ChannelSerializer(channel)
            return Response(response_serializer.data)
        return Response(
                {'status': 'Unauthorized', 'message': 'No access to this channel'},
                status=status.HTTP_401_UNAUTHORIZED
            )


class MessageViewSet(viewsets.ModelViewSet):
    """
    Message Resource
    """
    queryset = Message.objects.all().annotate(
        latest_reply_created_at=Max('replies__created_at')
    ).annotate(latest_created_at=Case(
        When(
            latest_reply_created_at__isnull=True,
            then='created_at'
        ),
        When(
            latest_reply_created_at__gt=F('created_at'),
            then='latest_reply_created_at'
        ),
        default='created_at',
        output_field=DateTimeField()
    )).order_by('-latest_created_at')
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated, DRYObjectPermissions]
    filter_class = MessageFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (MessageFilterBackend,)
    search_fields = ('user__username', 'body', 'replies__body')

    def perform_create(self, serializer):
        message = serializer.save()
        attachments = self.request.FILES
        if attachments:
            for file in attachments.itervalues():
                attachment = Attachment(content_object=message, file=file)
                attachment.save()

    @detail_route(
        methods=['post'], url_path='read',
        permission_classes=[IsAuthenticated]
    )
    def update_read(self, request, pk=None):
        """
        Set message as last_read in it's channel
        ---
        response_serializer: ChannelSerializer
        """
        message = get_object_or_404(self.get_queryset(), pk=pk)

        if message.has_object_read_permission(request):
            ChannelUser.objects.update_or_create(
                user=request.user, channel=message.channel, defaults={'last_read': message.id}
            )
            response_serializer = ChannelSerializer(message.channel)
            return Response(response_serializer.data)
        return Response(
                {'status': 'Unauthorized', 'message': 'No access to this message'},
                status=status.HTTP_401_UNAUTHORIZED
            )

