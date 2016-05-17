import datetime

from django.contrib.contenttypes.models import ContentType
from django.db.models.aggregates import Max
from django.db.models.expressions import Case, When, F
from django.db.models.fields import DateTimeField
from django.shortcuts import render
from dry_rest_permissions.generics import DRYObjectPermissions
from rest_framework import viewsets, status
from rest_framework.decorators import detail_route
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from tunga_messages.filterbackends import MessageFilterBackend, ReplyFilterBackend
from tunga_messages.filters import MessageFilter, ReplyFilter
from tunga_messages.models import Message, Reply, Reception, Attachment
from tunga_messages.serializers import MessageSerializer, ReplySerializer
from tunga_utils.filterbackends import DEFAULT_FILTER_BACKENDS


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
        content_type = ContentType.objects.get_for_model(Message)
        if attachments:
            for file in attachments.itervalues():
                attachment = Attachment(object_id=message.id, content_type=content_type, file=file)
                attachment.save()

    @detail_route(
        methods=['post'], url_path='read',
        permission_classes=[IsAuthenticated]
    )
    def update_read(self, request, pk=None):
        """
        Updates read_at of message thread
        """
        read_at = datetime.datetime.now()  # store read timestamp ASAP
        message = get_object_or_404(self.get_queryset(), pk=pk)

        if message.has_object_read_permission(request):
            if message.user == request.user:
                message.read_at = read_at
                message.save()
            else:
                reception = {'user': request.user, 'message': message, 'read_at': read_at}
                Reception.objects.update_or_create(user=request.user, message=message, defaults=reception)

            return Response({'status': 'Read status updated.', 'message': message.id})
        return Response(
                {'status': 'Unauthorized', 'message': 'No access to this message'},
                status=status.HTTP_401_UNAUTHORIZED
            )


class ReplyViewSet(viewsets.ModelViewSet):
    """
    Reply Resource
    """
    queryset = Reply.objects.all()
    serializer_class = ReplySerializer
    permission_classes = [IsAuthenticated, DRYObjectPermissions]
    filter_class = ReplyFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (ReplyFilterBackend,)
    search_fields = ('user__username', 'body')

    def perform_create(self, serializer):
        reply = serializer.save()
        attachments = self.request.FILES
        content_type = ContentType.objects.get_for_model(Reply)
        if attachments:
            for file in attachments.itervalues():
                attachment = Attachment(object_id=reply.id, content_type=content_type, file=file)
                attachment.save()
