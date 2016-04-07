from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from tunga_messages.filters import MessageFilter, ReplyFilter
from tunga_messages.models import Message, Reply
from tunga_messages.serializers import MessageSerializer, ReplySerializer


class MessageViewSet(viewsets.ModelViewSet):
    """
    Manage Messages
    """
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
    filter_class = MessageFilter
    search_fields = ('user__username', 'body', 'replies__body')


class ReplyViewSet(viewsets.ModelViewSet):
    """
    Manage Replies
    """
    queryset = Reply.objects.all()
    serializer_class = ReplySerializer
    permission_classes = [IsAuthenticated]
    filter_class = ReplyFilter
    search_fields = ('user__username', 'body')
