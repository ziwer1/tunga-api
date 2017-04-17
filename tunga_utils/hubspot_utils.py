import requests
from django.utils import six

from tunga.settings import HUBSPOT_API_KEY

HUBSPOT_API_BASE_URL = 'https://api.hubapi.com'
HUBSPOT_ENDPOINT_CREATE_UPDATE_CONTACT = '/contacts/v1/contact/createOrUpdate/email/{contact_email}'

KEY_VID = 'vid'


def get_hubspot_endpoint_url(endpoint):
    return '%s%s' % (HUBSPOT_API_BASE_URL, endpoint)


def get_authed_hubspot_endpoint_url(endpoint, api_key):
    return '%s?hapikey=%s' % (get_hubspot_endpoint_url(endpoint), api_key)


def create_hubspot_contact(email=None, **kwargs):
    if not email:
        return None

    properties = [
        dict(property='email', value=email)
    ]
    if kwargs:
        for key, value in six.iteritems(kwargs):
            properties.append(
                dict(property=key, value=value)
            )

    r = requests.post(
        get_authed_hubspot_endpoint_url(
            HUBSPOT_ENDPOINT_CREATE_UPDATE_CONTACT.format(contact_email=email), HUBSPOT_API_KEY
        ),
        json=dict(properties=properties)
    )

    if r.status_code in [200, 201]:
        response = r.json()
        return response
    return None
