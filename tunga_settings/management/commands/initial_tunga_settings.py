from django.core.management.base import BaseCommand
from django.utils import six

from tunga_settings import slugs
from tunga_settings.models import VISIBILITY_CHOICES, SwitchSetting, VisibilitySetting, UserSwitchSetting


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
                'slug': slugs.DAILY_UPDATE_EMAIL,
                'name': 'Daily update e-mail',
                'default_value': True,
                'description': 'You will receive an email with the notifications of a specific day. '
                               'No notification = no email'
            },
            # Messages
            {'slug': slugs.DIRECT_MESSAGES_EMAIL, 'name': 'Direct messages', 'default_value': True},

            # Connections
            {'slug': slugs.NEW_FRIEND_REQUEST_EMAIL, 'name': 'New friend request', 'default_value': True},
            {'slug': slugs.TEAM_INVITATION_RESPONSE_EMAIL, 'name': 'Response to team invitation', 'default_value': True},
            {'slug': slugs.FRIEND_REQUEST_RESPONSE_EMAIL, 'name': 'Response to friend request', 'default_value': True},
            {'slug': slugs.JOIN_TEAM_REQUEST_RESPONSE_EMAIL, 'name': 'Response to join team request', 'default_value': True},
            {'slug': slugs.NEW_TEAM_INVITATION_EMAIL, 'name': 'Invitation to join a team', 'default_value': True},

            # Tasks
            {'slug': slugs.NEW_TASK_EMAIL, 'name': 'New task created', 'default_value': True},
            {'slug': slugs.NEW_TASK_APPLICATION_EMAIL, 'name': 'New application for a task', 'default_value': True},
            {
                'slug': slugs.TASK_APPLICATION_RESPONSE_EMAIL,
                'name': 'Task application accepted or rejected',
                'default_value': True
            },
            {'slug': slugs.NEW_TASK_INVITATION_EMAIL, 'name': 'Invitation to a task', 'default_value': True},
            {
                'slug': slugs.TASK_INVITATION_RESPONSE_EMAIL,
                'name': 'Task invitation accepted or rejected',
                'default_value': True
            },
            {
                'slug': slugs.TASK_PROGRESS_REPORT_REMINDER_EMAIL,
                'name': 'Reminders about upcoming reports for milestones and scheduled updates',
                'default_value': True
            },
            {'slug': slugs.TASK_ACTIVITY_UPDATE_EMAIL, 'name': 'Task activity updates', 'default_value': True},

            # Payments
            {'slug': slugs.PAYMENT_REQUEST_EMAIL, 'name': 'Payment requests', 'default_value': True},
            {'slug': slugs.PAYMENT_UPDATE_EMAIL, 'name': 'Payment updates', 'default_value': True},
        ]

        num_created = 0

        for setting in visibility_settings:
            new_setting, created = VisibilitySetting.objects.update_or_create(slug=setting['slug'], defaults=setting)
            if created:
                num_created += 1

        for setting in switch_settings:
            new_setting, created = SwitchSetting.objects.update_or_create(slug=setting['slug'], defaults=setting)
            if created:
                num_created += 1

        print("%s settings added" % num_created)

        slug_map = {
            slugs.TASK_APPLICATION_RESPONSE_EMAIL: 'new_task_application_response_email',
            slugs.TASK_INVITATION_RESPONSE_EMAIL: 'new_task_invitation_response_email',
            slugs.TASK_ACTIVITY_UPDATE_EMAIL: 'task_update_email'
        }

        for new_slug, old_slug in six.iteritems(slug_map):
            r = UserSwitchSetting.objects.filter(setting__slug=old_slug).update(setting=new_slug)
            print(r, new_slug)

        if slug_map:
            old_slugs = [slug for slug in six.itervalues(slug_map)]
            print(SwitchSetting.objects.filter(slug__in=old_slugs).delete())
