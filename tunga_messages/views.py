import json
import re

import datetime
from django.views.decorators.csrf import csrf_exempt
from dry_rest_permissions.generics import DRYObjectPermissions, DRYPermissions
from rest_framework import viewsets, status
from rest_framework.decorators import detail_route, list_route, api_view, permission_classes
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.response import Response

from tunga_activity.filters import ActionFilter, MessageActivityFilter
from tunga_activity.serializers import SimpleActivitySerializer, LastReadActivitySerializer
from tunga_messages.filterbackends import MessageFilterBackend, ChannelFilterBackend
from tunga_messages.filters import MessageFilter, ChannelFilter
from tunga_messages.models import Message, Channel, ChannelUser
from tunga_messages.serializers import MessageSerializer, ChannelSerializer, DirectChannelSerializer, \
    SupportChannelSerializer, DeveloperChannelSerializer
from tunga_messages.tasks import get_or_create_direct_channel, get_or_create_support_channel, create_channel, \
    get_or_create_task_channel
from tunga_messages.utils import annotate_channel_queryset_with_latest_activity_at
from tunga_profiles.models import Inquirer
from tunga_tasks.models import Task
from tunga_utils import slack_utils
from tunga_utils.constants import CHANNEL_TYPE_SUPPORT, APP_INTEGRATION_PROVIDER_SLACK, CHANNEL_TYPE_DEVELOPER
from tunga_utils.filterbackends import DEFAULT_FILTER_BACKENDS
from tunga_utils.mixins import SaveUploadsMixin
from tunga_utils.pagination import LargeResultsSetPagination, DefaultPagination


class ChannelViewSet(viewsets.ModelViewSet, SaveUploadsMixin):
    """
    Channel Resource
    """
    queryset = Channel.objects.all()
    serializer_class = ChannelSerializer
    permission_classes = [DRYPermissions, DRYObjectPermissions]
    filter_class = ChannelFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (ChannelFilterBackend,)
    pagination_class = LargeResultsSetPagination
    search_fields = (
        'subject', 'channeluser__user__username', 'channeluser__user__first_name',
        'channeluser__user__last_name'
    )

    def get_queryset(self):
        return annotate_channel_queryset_with_latest_activity_at(
            self.queryset, self.request.user
        ).distinct().order_by('-latest_activity_at')

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

    @list_route(
        methods=['post'], url_path='support',
        permission_classes=[AllowAny], serializer_class=SupportChannelSerializer
    )
    def support_channel(self, request):
        """
        Gets or creates a direct channel for the current user or customer
        ---
        request_serializer: SupportChannelSerializer
        response_serializer: ChannelSerializer
        """

        serializer = self.get_serializer(data=request.data)
        channel = None
        if serializer.is_valid(raise_exception=True):
            if request.user.is_authenticated():
                # Create support channel for logged in user
                channel = get_or_create_support_channel(request.user)
            else:
                # Create support channel for anonymous user
                channel_id = serializer.validated_data.get('id', None)
                if channel_id:
                    channel = get_object_or_404(self.get_queryset(), pk=channel_id)
                    email = serializer.validated_data.get('email', None)
                    name = serializer.validated_data.get('name', None)
                    if email:
                        customer = Inquirer.objects.create(name=name, email=email)
                        channel.content_object = customer
                        channel.save()
                    else:
                        return Response(
                            {'email': "Couldn't get or create a support channel"},
                            status=status.HTTP_400_BAD_REQUEST
                        )

                else:
                    channel = Channel.objects.create(type=CHANNEL_TYPE_SUPPORT)#, content_object=customer)
        if not channel:
            return Response(
                {'status': "Couldn't get or create a support channel"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        response_serializer = ChannelSerializer(channel, context={'request': request})
        return Response(response_serializer.data)

    @list_route(
        methods=['post'], url_path='developer',
        permission_classes=[IsAdminUser], serializer_class=DeveloperChannelSerializer
    )
    def developer_channel(self, request):
        """
        Gets or creates a developer channel for the current user
        ---
        request_serializer: DeveloperChannelSerializer
        response_serializer: ChannelSerializer
        """

        serializer = self.get_serializer(data=request.data)
        channel = None
        if serializer.is_valid(raise_exception=True):
            # Create developer channel
            subject = serializer.validated_data['subject']
            message = serializer.validated_data['message']
            channel = create_channel(
                request.user,
                channel_type=CHANNEL_TYPE_DEVELOPER,
                subject=subject,
                messages=[
                    dict(user=request.user, body=message)
                ]
            )
        if not channel:
            return Response(
                {'status': "Couldn't get or create a support channel"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        response_serializer = ChannelSerializer(channel, context={'request': request})
        return Response(response_serializer.data)

    @list_route(
        methods=['post'], url_path='task/(?P<task_id>[^/]+)',
        permission_classes=[IsAuthenticated]
    )
    def task_channel(self, request, task_id=None):
        """
        Gets or creates task channel
        ---
        response_serializer: ChannelSerializer
        """

        task = get_object_or_404(Task.objects.all(), pk=task_id)
        channel = None
        if task:
            channel = get_or_create_task_channel(request.user, task)
        if not channel:
            return Response(
                {'status': "Couldn't create task channel"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        response_serializer = ChannelSerializer(channel, context={'request': request})
        return Response(response_serializer.data)

    @detail_route(
        methods=['post'], url_path='read',
        permission_classes=[AllowAny], serializer_class=LastReadActivitySerializer
    )
    def update_read(self, request, pk=None):
        """
        Updates user's read_at for channel
        ---
        request_serializer: LastReadActivitySerializer
        response_serializer: ChannelSerializer
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        last_read = serializer.validated_data['last_read']
        channel = get_object_or_404(self.get_queryset(), pk=pk)
        if channel.has_object_read_permission(request):
            if request.user.is_authenticated():
                ChannelUser.objects.update_or_create(
                    user=request.user, channel=channel, defaults={'last_read': last_read}
                )
            else:
                channel.last_read = last_read
                channel.save()
            response_serializer = ChannelSerializer(channel, context={'request': request})
            return Response(response_serializer.data)
        return Response(
                {'status': 'Unauthorized', 'message': 'No access to this channel'},
                status=status.HTTP_401_UNAUTHORIZED
            )

    @detail_route(
        methods=['get'], url_path='activity',
        permission_classes=[AllowAny],
        serializer_class=SimpleActivitySerializer,
        filter_class=None,
        filter_backends=DEFAULT_FILTER_BACKENDS,
        search_fields=('messages__body', 'uploads__file', 'messages__attachments__file'),
        pagination_class=DefaultPagination
    )
    def activity(self, request, pk=None):
        """
        Channel Activity Endpoint
        ---
        response_serializer: SimpleActivitySerializer
        #omit_parameters:
        #    - query
        """
        channel = get_object_or_404(self.get_queryset(), pk=pk)
        self.check_object_permissions(request, channel)
        if not channel.has_object_read_permission(request):
            return Response(
                {'status': 'Unauthorized', 'message': 'No access to this channel'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        queryset = MessageActivityFilter(
            request.GET,
            self.filter_queryset(channel.target_actions.all().order_by('-id'))
        )
        page = self.paginate_queryset(queryset.qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class MessageViewSet(viewsets.ModelViewSet, SaveUploadsMixin):
    """
    Message Resource
    """
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    permission_classes = [DRYPermissions, DRYObjectPermissions]
    filter_class = MessageFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (MessageFilterBackend,)
    search_fields = ('user__username', 'body',)

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


@csrf_exempt
@api_view(http_method_names=['POST'])
@permission_classes([AllowAny])
def slack_customer_notification(request):
    payload = request.data

    # Verify that the request came from Slack
    if not slack_utils.verify_webhook_token(payload.get(slack_utils.KEY_TOKEN, None)):
        return Response('Unauthorized Request', status=status.HTTP_401_UNAUTHORIZED)

    response = None
    if payload and not payload.get(slack_utils.KEY_BOT_ID, None):
        text = payload.get(slack_utils.KEY_TEXT, None)
        m = re.match(r'^[\*`_~]{0,3}C(?P<id>\d+)[\*`_~]{0,3}(?P<message>.*)', text, flags=re.DOTALL | re.IGNORECASE)
        if m:
            matches = m.groupdict()
            message = matches.get('message', '').strip()
            channel_id = matches.get('id', '')
            try:
                slack_user = dict(
                    id=payload.get(slack_utils.KEY_USER_ID, None),
                    name=payload.get(slack_utils.KEY_USER_NAME, None),
                    provider=APP_INTEGRATION_PROVIDER_SLACK
                )
                msg_extras = dict(
                    channel=dict(
                        id=payload.get(slack_utils.KEY_CHANNEL_ID),
                        name=payload.get(slack_utils.KEY_CHANNEL_NAME)
                    ),
                    team=dict(
                        id=payload.get(slack_utils.KEY_TEAM_ID),
                        domain=payload.get(slack_utils.KEY_TEAM_DOMAIN)
                    ),
                    timestamp=payload.get(slack_utils.KEY_TS, None)
                )
                Message.objects.create(
                    channel_id=channel_id,
                    body=message,
                    alt_user=json.dumps(slack_user),
                    created_at=datetime.datetime.fromtimestamp(payload.get(slack_utils.KEY_TS, 0)),
                    source=APP_INTEGRATION_PROVIDER_SLACK,
                    extra=json.dumps(msg_extras)
                )
            except:
                response = 'Failed to send message\n' \
                           '> %s\n' \
                           'Please try again' % message
        else:
            response = 'Failed to send message\n' \
                       '> %s\n' \
                       'Please add a target and re-send the message' % text
    return Response({slack_utils.KEY_TEXT: response, slack_utils.KEY_MRKDWN: True})
