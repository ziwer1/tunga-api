import json

import requests

from tunga.settings import SLACK_CUSTOMER_OUTGOING_WEBHOOK_TOKEN, SLACK_AUTHORIZE_URL, SLACK_SCOPES, SLACK_CLIENT_ID, \
    SLACK_ACCESS_TOKEN_URL
from tunga_utils.constants import APP_INTEGRATION_PROVIDER_SLACK
from tunga_utils.helpers import get_app_integration

KEY_TOKEN = 'token'
KEY_TEAM_ID = 'team_id'
KEY_TEAM_DOMAIN = 'team_domain'
KEY_CHANNEL_ID = 'channel_id'
KEY_CHANNEL_NAME = 'channel_name'
KEY_USER_ID = 'user_id'
KEY_USER_NAME = 'user_name'
KEY_TEXT = 'text'
KEY_TRIGGER_WORD = 'trigger_word'
KEY_TIMESTAMP = 'timestamp'
KEY_BOT_ID = 'bot_id'
KEY_BOT_NAME = 'bot_name'
KEY_SERVICE_ID = 'service_id'
KEY_USERNAME = 'username'
KEY_ICON_URL = 'icon_url'
KEY_ICON_EMOJI = 'icon_emoji'
KEY_ATTACHMENTS = 'attachments'
KEY_COLOR = 'color'
KEY_FALLBACK = 'fallback'
KEY_PRETEXT = 'pretext'
KEY_AUTHOR_NAME = 'author_name'
KEY_AUTHOR_LINK = 'author_link'
KEY_AUTHOR_ICON = 'author_icon'
KEY_TITLE = 'title'
KEY_TITLE_LINK = 'title_link'
KEY_FIELDS = 'fields'
KEY_VALUE = 'value'
KEY_SHORT = 'short'
KEY_IMAGE_URL = 'image_url'
KEY_THUMB_URL = 'thumb_url'
KEY_FOOTER = 'footer'
KEY_FOOTER_ICON = 'footer_icon'
KEY_TS = 'ts'
KEY_MRKDWN = 'mrkdwn'
KEY_MRKDWN_IN = 'mrkdwn_in'


def get_authorize_url(redirect_uri):
    return '%s?client_id=%s&scope=%s&redirect_uri=%s' % (
        SLACK_AUTHORIZE_URL, SLACK_CLIENT_ID, ','.join(SLACK_SCOPES), redirect_uri
    )


def get_token_url():
    return SLACK_ACCESS_TOKEN_URL


def get_webhook_url(user):
    app_integration = get_app_integration(user=user, provider=APP_INTEGRATION_PROVIDER_SLACK)
    if app_integration and app_integration.extra:
        extra = json.loads(app_integration.extra)
        incoming_webhook = extra.get('incoming_webhook', None)
        if incoming_webhook:
            return incoming_webhook.get('url', None)
    return None


def verify_webhook_token(token):
    return token == SLACK_CUSTOMER_OUTGOING_WEBHOOK_TOKEN


def is_task_notification_enabled(task, event_id):
    return task.integration_set.filter(provider=APP_INTEGRATION_PROVIDER_SLACK, events__id=event_id).count() > 0


def send_incoming_webhook(url, message):
    requests.post(url, json=message)
