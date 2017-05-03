import requests
from django.utils import six
import json

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

def get_hubspot_account_pipelines():
    r = requests.get('http://api.hubapi.com/deals/v1/pipelines?hapikey=%s' % (HUBSPOT_API_KEY))

    if r.status_code in [200, 201]:
        return r


def get_hubspot_owner_id(email):
    r = requests.get('http://api.hubapi.com/owners/v2/owners?hapikey=demo&email=%s' % (email))

    if r.status_code in [200, 201]:
        owner_id = json.loads(json.dumps(r.json()))[0]['remoteList'][0]['ownerId']
        return owner_id

def get_hubspot_contact_vid(email):
    r = requests.get('https://api.hubapi.com/contacts/v1/contact/email/%s/profile?hapikey=%s' % (email,HUBSPOT_API_KEY))

    if r.status_code in [200, 201]:
        vid = json.loads(json.dumps(r.json()))['canonical-vid']
        return vid


def create_hubspot_deal(task):
    
    url = "https://api.hubapi.com/deals/v1/deal"

    querystring = {"hapikey":HUBSPOT_API_KEY}

    payload = "{\r\n  \"associations\": {\r\n    \"associatedVids\": [\r\n   \
       %d\r\n    ]\r\n  },\r\n  \"properties\": [\r\n    {\r\n      \"value\":\
        \"%s\",\r\n      \"name\": \"dealname\"\r\n    },\r\n    {\r\n      \
        \"value\": \"4d333654-0391-47e9-b1d2-9cb16effafc9\",\r\n      \"name\": \
        \"dealstage\"\r\n    },\r\n    {\r\n      \"value\": \"a053401c-4ea5-4075-abc1-bd5f44e9b0f3\",\r\n      \
        \"name\": \"pipeline\"\r\n    },\r\n    {\r\n      \"value\": \"16208186\",\r\n      \
        \"name\": \"hubspot_owner_id\"\r\n    },\r\n    {\r\n      \
        \"value\": 1409443200000,\r\n      \"name\": \"closedate\"\r\n    },\r\n    \
        {\r\n      \"value\": \"%d\",\r\n      \"name\": \"amount\"\r\n    },\r\n    \
        {\r\n      \"value\": \"%d\",\r\n      \"name\": \"task_id\"\r\n    },\r\n    \
        {\r\n      \"value\": \"%s\",\r\n      \"name\": \"description\"\r\n    },\r\n    \
        {\r\n      \"value\": \"newbusiness\",\r\n      \"name\": \"dealtype\"\r\n    }\r\n  \
        ]\r\n}" % (get_hubspot_contact_vid(task.user.email), task.title, int(task.fee), task.id, task.description)

    headers = {
        'content-type': "application/json",
        'cache-control': "no-cache" }

    response = requests.request("POST", url, data=payload, headers=headers, params=querystring)




