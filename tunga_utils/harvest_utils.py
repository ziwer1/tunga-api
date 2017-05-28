import json

import harvest
from django.utils import six
import requests

from tunga.settings import HARVEST_CLIENT_ID, HARVEST_API_URL, HARVEST_CLIENT_SECRET, HARVEST_ACCOUNT, \
    HARVEST_AUTHENTICATION_STRING
from tunga_profiles.models import AppIntegration
from tunga_utils.constants import APP_INTEGRATION_PROVIDER_HARVEST

HARVEST_API_USER_URL = 'https://%s.harvestapp.com/people' % (HARVEST_ACCOUNT)
HARVEST_HEADERS = {'accept': 'application/json', 'content-type':'application/json', 'authorization': 'Basic %s' % (HARVEST_AUTHENTICATION_STRING)}


def get_authorize_url(redirect_uri):
    return '%s/oauth2/authorize?client_id=%s&redirect_uri=%s&response_type=code' % (
        HARVEST_API_URL, HARVEST_CLIENT_ID, redirect_uri
    )


def get_token_url():
    return '%s/oauth2/token' % HARVEST_API_URL


def get_api_client(token, user=None, return_response_obj=True):
    return harvest.Harvest(
        HARVEST_API_URL,
        client_id=HARVEST_CLIENT_ID, client_secret=HARVEST_CLIENT_SECRET,
        token=token, token_updater=store_token, context=dict(user=user), return_response_obj=return_response_obj
    )


def store_token(token, **kwargs):
    defaults = {
        'token': token['access_token'],
        'token_secret': token['refresh_token'],
        'extra': json.dumps(token)
    }
    user = kwargs.get('user', None)
    if user:
        AppIntegration.objects.update_or_create(
            user=user, provider=APP_INTEGRATION_PROVIDER_HARVEST, defaults=defaults
        )

def create_user(first_name, last_name, email, **kwargs):
    user = {'first_name': first_name, 'last_name':last_name, 'email':email}
    
    if kwargs:
        for key, value in six.iteritems(kwargs):
            user[key] = value;

    payload = {'user': user}

    r = requests.post(HARVEST_API_USER_URL, headers=HARVEST_HEADERS, json=payload)

