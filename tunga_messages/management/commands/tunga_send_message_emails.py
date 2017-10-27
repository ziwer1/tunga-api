# -*- coding: utf-8 -*-

import datetime

from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand
from django.db.models.aggregates import Sum
from django.db.models.expressions import Case, When, F
from django.db.models.fields import IntegerField
from django.db.models.query_utils import Q

from tunga.settings import TUNGA_URL
from tunga_activity import verbs
from tunga_messages.models import ChannelUser
from tunga_utils.constants import CHANNEL_TYPE_DIRECT
from tunga_utils.emails import send_mail


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Send new message notifications
        """
        # command to run: python manage.py tunga_send_message_emails
        utc_now = datetime.datetime.utcnow()
        min_date = utc_now - relativedelta(minutes=15)  # 15 minute window to read new messages
        min_last_email_date = utc_now - relativedelta(hours=3)  # Limit to 1 email every 3 hours per channel
        commission_date = parse('2016-08-08 00:00:00')  # Don't notify about events before the commissioning date

        user_channels = ChannelUser.objects.filter(
            Q(last_email_at__isnull=True) |
            Q(last_email_at__lt=min_last_email_date)
        ).annotate(new_messages=Sum(
            Case(
                When(
                    ~Q(channel__action_targets__actor_object_id=F('user_id')) &
                    Q(channel__action_targets__gt=F('last_read')) &
                    Q(channel__action_targets__timestamp__lte=min_date) &
                    Q(channel__action_targets__timestamp__gte=commission_date) &
                    (Q(last_email_at__isnull=True) | Q(channel__action_targets__timestamp__gt=F('last_email_at'))) &
                    Q(channel__action_targets__verb__in=[verbs.SEND, verbs.UPLOAD]),
                    then=1
                ),
                default=0,
                output_field=IntegerField()
            )
        )).filter(new_messages__gt=0)

        for user_channel in user_channels:
            channel_name = user_channel.channel.get_channel_display_name(user_channel.user)

            to = [user_channel.user.email]
            if user_channel.channel.type == CHANNEL_TYPE_DIRECT:
                conversation_subject = "New message{} from {}".format(
                    user_channel.new_messages == 1 and '' or 's',
                    channel_name
                )
            else:
                conversation_subject = "Conversation: {}".format(channel_name)
            subject = conversation_subject
            ctx = {
                'receiver': user_channel.user,
                'new_messages': user_channel.new_messages,
                'channel_name': channel_name,
                'channel': user_channel.channel,
                'channel_url': '%s/conversation/%s/' % (TUNGA_URL, user_channel.channel.id)
            }

            if send_mail(subject, 'tunga/email/unread_channel_messages', to, ctx):
                user_channel.last_email_at = datetime.datetime.utcnow()
                user_channel.save()
