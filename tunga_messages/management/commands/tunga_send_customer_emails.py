# -*- coding: utf-8 -*-

import datetime

from actstream.models import Action
from dateutil.relativedelta import relativedelta
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db.models.aggregates import Sum, Max
from django.db.models.expressions import Case, When, F
from django.db.models.fields import IntegerField
from django.db.models.query_utils import Q

from tunga.settings import TUNGA_URL
from tunga_activity import verbs
from tunga_messages.models import Channel
from tunga_profiles.models import Inquirer
from tunga_utils.constants import CHANNEL_TYPE_SUPPORT
from tunga_utils.emails import send_mail


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Send new message notifications
        """
        # command to run: python manage.py tunga_send_customer_emails
        min_date = datetime.datetime.utcnow() - relativedelta(minutes=1)  # 5 minute window to read new messages

        customer_channels = Channel.objects.filter(
            type=CHANNEL_TYPE_SUPPORT,
            created_by__isnull=True,
            content_type=ContentType.objects.get_for_model(Inquirer)
        ).annotate(new_messages=Sum(
            Case(
                When(
                    ~Q(action_targets__actor_content_type=F('content_type')) &
                    Q(action_targets__gt=F('last_read')) &
                    Q(action_targets__timestamp__lte=min_date) &
                    Q(action_targets__verb__in=[verbs.SEND, verbs.UPLOAD]),
                    then=1
                ),
                default=0,
                output_field=IntegerField()
            )
        ), latest_message=Max('action_targets__id')).filter(new_messages__gt=0)

        for channel in customer_channels:
            customer = channel.content_object
            if customer.email:
                activities = Action.objects.filter(
                    channels=channel, id__gt=channel.last_read, verb__in=[verbs.SEND]
                ).order_by('id')

                messages = [activity.action_object for activity in activities]

                if messages:
                    to = [customer.email]
                    subject = "[Tunga Support] Help"
                    ctx = {
                        'customer': customer,
                        'count': channel.new_messages,
                        'messages': messages,
                        'channel_url': '%s/customer/help/%s/' % (TUNGA_URL, channel.id)
                    }

                    if send_mail(subject, 'tunga/email/unread_help_messages', to, ctx):
                        channel.last_read = channel.latest_message
                        channel.save()
