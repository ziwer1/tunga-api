from django.core.management.base import BaseCommand

from tunga_settings import slugs
from tunga_settings.models import VISIBILITY_CHOICES, SwitchSetting, VisibilitySetting


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Creates default settings.
        """
        # command to run: python manage.py initial_tunga_settings

        visibility_settings = [
            {'slug': slugs.PROFILE_VISIBILITY, 'name': 'Profile visibility', 'default_value': VISIBILITY_CHOICES[0][0]},
            {'slug': slugs.SOCIAL_LINKS, 'name': 'Social links', 'default_value': VISIBILITY_CHOICES[0][0]},
            {'slug': slugs.LOCATION_DETAILS, 'name': 'Location details', 'default_value': VISIBILITY_CHOICES[0][0]},
        ]

        switch_settings = [
            {
                'slug': slugs.DAILY_UPDATE_EMAIL, 'name': 'Daily update e-mail', 'default_value': True,
                'description': 'You will receive an email with the notifications of a specific day. No notification = no email'
            },
            {'slug': slugs.DIRECT_MESSAGES_EMAIL, 'name': 'Direct messages', 'default_value': True},
            {'slug': slugs.NEW_FRIEND_REQUEST_EMAIL, 'name': 'New friend request', 'default_value': True},
            {'slug': slugs.TEAM_INVITATION_RESPONSE_EMAIL, 'name': 'Reply from developer on invitation', 'default_value': True},
            {'slug': slugs.FRIEND_REQUEST_RESPONSE_EMAIL, 'name': 'Reply to friend request', 'default_value': True},
            {'slug': slugs.JOIN_TEAM_REQUEST_RESPONSE_EMAIL, 'name': 'Reply to join team request', 'default_value': True},
            {'slug': slugs.NEW_TEAM_INVITATION_EMAIL, 'name': 'Invitation to join a team', 'default_value': True},
            {'slug': slugs.NEW_TASK_APPLICATION_EMAIL, 'name': 'New application for a task', 'default_value': True},
            {'slug': slugs.TASK_UPDATE_EMAIL, 'name': 'Task updates', 'default_value': True},
            {'slug': slugs.PAYMENT_REQUEST_EMAIL, 'name': 'Payment requests', 'default_value': True},
            {'slug': slugs.PAYMENT_UPDATE_EMAIL, 'name': 'Payment updates', 'default_value': True},
        ]

        for setting in visibility_settings:
            VisibilitySetting.objects.update_or_create(slug=setting['slug'], defaults=setting)

        for setting in switch_settings:
            SwitchSetting.objects.update_or_create(slug=setting['slug'], defaults=setting)

        print "%s settings added" % (len(visibility_settings) + len(switch_settings))
