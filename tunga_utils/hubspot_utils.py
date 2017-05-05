import requests
from django.utils import six
import json
import re
from django.template.exceptions import TemplateDoesNotExist
from django.template.loader import render_to_string
from tunga.settings import DEFAULT_FROM_EMAIL, EMAIL_SUBJECT_PREFIX
from tunga_utils.helpers import convert_to_text


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
    else:
        response = create_hubspot_contact(email)
        response = response['vid']
        return response


def create_hubspot_deal(task):

    payload = json.loads('{"associations":{"associatedCompanyIds":[],"associatedVids":[]},"properties":[]}')

    payload['associations']['associatedVids'].insert(0,get_hubspot_contact_vid(task.user.email))
    
    payload['properties'].extend([{"value":task.title,"name":"dealname"},{"value":"appointmentscheduled",\
        "name":"dealstage"},{"value":"default","name":"pipeline"},{"value":str(int(task.fee)),"name":"amount"},\
        {"value":"newbusiness","name":"dealtype"}])
    
    #production
    #payload['properties'].extend([{"value":task.id,"name":"task_id"},{"value":task.description,"name":"description"}])

    url = 'https://api.hubapi.com/deals/v1/deal?hapikey=%s' % (HUBSPOT_API_KEY)

    response = requests.post(url, json=payload)



def create_hubspot_engagement(subject, template_prefix, to_emails, context, bcc=None, cc=None, **kwargs):
    from_email = DEFAULT_FROM_EMAIL
    if not re.match(r'^\[\s*Tunga', subject):
        subject = '{} {}'.format(EMAIL_SUBJECT_PREFIX, subject)

    bodies = {}
    for ext in ['html', 'txt']:
        try:
            template_name = '{0}.{1}'.format(template_prefix, ext)
            bodies[ext] = render_to_string(template_name,
                                           context).strip()
        except TemplateDoesNotExist:
            if ext == 'txt':
                if 'html' in bodies:
                    # Compose text body from html
                    bodies[ext] = convert_to_text(bodies['html'])
                else:
                    # We need at least one body
                    raise

    if bodies:

        bodies['html'] = bodies['html'].replace('"', "'")

        payload = json.loads('{"engagement":{"active":true,"ownerId":70,"type":"EMAIL"},\
        "associations":{"contactIds":[],"companyIds":[],"dealIds":[],"ownerIds":[]},\
        "metadata":{"from":{"email":"","firstName":"Tunga","lastName":"Support"},\
        "to":[{"email":"This contact"}],"cc":[],"bcc":[],"subject":"","html":"","text":""}}')

        contactIds = []
        for email in to_emails:
            contactIds.insert(0,get_hubspot_contact_vid(email))

        payload['engagement']['ownerId'] = 16208186
        payload['associations']['contactIds'].extend(contactIds)
        payload['metadata']['from']['email'] = DEFAULT_FROM_EMAIL
        payload['metadata']['subject'] = subject
        payload['metadata']['html'] = bodies['html']
        payload['metadata']['txt'] = bodies['txt']

        url = 'https://api.hubapi.com/engagements/v1/engagements?hapikey=%s' % (HUBSPOT_API_KEY)

        response = requests.post(url, json=payload)



    else:
        raise TemplateDoesNotExist

