import json
from django.utils import six

from allauth.socialaccount.providers.github.provider import GitHubProvider

from tunga_profiles.utils import get_app_integration
from tunga_tasks.models import Integration, IntegrationMeta
from tunga_utils.constants import APP_INTEGRATION_PROVIDER_SLACK, APP_INTEGRATION_PROVIDER_HARVEST, STATUS_ACCEPTED
from tunga_utils.helpers import clean_meta_value, get_social_token, GenericObject


def get_task_integration(task, provider):
    try:
        return Integration.objects.filter(task_id=task, provider=provider).latest('updated_at')
    except Integration.DoesNotExist:
        return None


def get_integration_token(user, provider, task=None):
    if task:
        task_integration = get_task_integration(task, provider)
        if task_integration and task_integration.token:
            return GenericObject(
                **dict(
                    token=task_integration.token,
                    token_secret=task_integration.token_secret,
                    extra=task_integration.token_extra
                )
            )

    if provider == GitHubProvider.id:
        return get_social_token(user=user, provider=provider)
    else:
        return get_app_integration(user=user, provider=provider)


def save_task_integration_meta(task_id, provider, meta_info):
    integration = get_task_integration(task_id, provider)

    if integration and isinstance(meta_info, dict):
        for meta_key in meta_info:
            IntegrationMeta.objects.update_or_create(
                integration=integration, meta_key=meta_key, defaults=dict(meta_value=clean_meta_value(meta_info[meta_key]))
            )


def save_integration_tokens(user, task_id, provider):
    token_info = dict()
    if provider == GitHubProvider.id:
        social_token = get_social_token(user=user, provider=provider)
        if social_token:
            token_info = dict(
                token=social_token.token,
                token_secret=social_token.token_secret,
                token_expires_at=social_token.expires_at
            )
    else:
        app_integration = get_app_integration(user=user, provider=provider)
        if app_integration:
            token_info = dict(
                token=app_integration.token,
                token_secret=app_integration.token_secret,
                token_expires_at=app_integration.expires_at,
                token_extra=app_integration.extra
            )

            if provider == APP_INTEGRATION_PROVIDER_SLACK:
                token_info.pop('token_secret')
                response = json.loads(app_integration.extra)
                if 'bot' in response:
                    token_info['bot_access_token'] = response['bot'].get('bot_access_token')
                    token_info['bot_user_id'] = response['bot'].get('bot_user_id')
            elif provider == APP_INTEGRATION_PROVIDER_HARVEST:
                token_info.pop('token_secret')
                token_info['refresh_token'] = app_integration.token_secret
    save_task_integration_meta(task_id, provider, token_info)

def get_developers_contacts_list(task):

    all_developers = ''
    participants_info = []
    participants = task.participation_set.filter(status=STATUS_ACCEPTED)

    if participants:
        for participant in participants:
            participants_info.append({participant.user.first_name:participant.user.email})

    if participants_info:
        for participant_info in participants_info:
            for key, value in six.iteritems(participant_info):
                    all_developers += '%s : %s | ' % (key, value)

    return all_developers
