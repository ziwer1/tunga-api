import os

import datetime
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.files.base import File
from django.core.management.base import BaseCommand

from tunga.settings.base import MEDIA_ROOT
from tunga_settings.models import VISIBILITY_CHOICES, SwitchSetting, VisibilitySetting


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Creates all auth emails for all wordpress users.
        """
        # command to run: python manage.py initial_tunga_settings

        visibility_settings = [
            {'slug': 'profile_visibility', 'name': 'Profile visibility', 'default_value': VISIBILITY_CHOICES[0][0]},
            {'slug': 'social_links', 'name': 'Social links', 'default_value': VISIBILITY_CHOICES[0][0]},
            {'slug': 'location_details', 'name': 'Location details', 'default_value': VISIBILITY_CHOICES[0][0]},
        ]

        switch_settings = [
            {
                'slug': 'daily_update_email', 'name': 'Daily update e-mail', 'default_value': True,
                'description': 'You will receive an email with the notifications of a specific day. No notification = no email'
            },
            {'slug': 'direct_messages_email', 'name': 'Direct messages', 'default_value': True},
            {'slug': 'new_friend_request_email', 'name': 'New friend request', 'default_value': True},
            {'slug': 'team_invitation_response_email', 'name': 'Reply from developer on invitation', 'default_value': True},
            {'slug': 'friend_request_response_email', 'name': 'Reply to friend request', 'default_value': True},
            {'slug': 'join_team_request_response_email', 'name': 'Reply to join team request', 'default_value': True},
            {'slug': 'new_team_invitation_email', 'name': 'Invitation to join a team', 'default_value': True},
            {'slug': 'new_task_application_email', 'name': 'New application for a task', 'default_value': True},
            {'slug': 'task_update_email', 'name': 'Task updates', 'default_value': True},
            {'slug': 'payment_request_email', 'name': 'Payment requests', 'default_value': True},
        ]

        for setting in visibility_settings:
            VisibilitySetting.objects.update_or_create(slug=setting['slug'], defaults=setting)

        for setting in switch_settings:
            SwitchSetting.objects.update_or_create(slug=setting['slug'], defaults=setting)

        print "%s settings added" % (len(visibility_settings) + len(switch_settings))
