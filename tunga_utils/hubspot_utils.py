import requests
from django.utils import six


from tunga.settings import HUBSPOT_API_KEY

HUBSPOT_API_BASE_URL = 'https://api.hubapi.com'
HUBSPOT_ENDPOINT_CREATE_UPDATE_CONTACT = '/contacts/v1/contact/createOrUpdate/email/{contact_email}'
HUBSPOT_ENDPOINT_CREATE_DEAL = '/deals/v1/deal'
HUBSPOT_ENDPOINT_CREATE_DEAL_PROPERTY = '/properties/v1/deals/properties/'
HUBSPOT_ENDPOINT_CREATE_ENGAGEMENT = '/engagements/v1/engagements'

KEY_VID = 'vid'
KEY_NAME = 'name'
KEY_LABEL = 'label'
KEY_DESCRIPTION = 'description'
KEY_TYPE = 'type'
KEY_FIELDTYPE = 'fieldType'
KEY_GROUPNAME = 'groupName'
KEY_DEALNAME = 'dealname'
KEY_DEALSTAGE = 'dealstage'
KEY_DEALTYPE = 'dealtype'
KEY_PIPELINE = 'pipeline'
KEY_AMOUNT = 'amount'

KEY_VALUE_APPOINTMENT_SCHEDULED = 'appointmentscheduled'
KEY_VALUE_DEFAULT = 'default'
KEY_VALUE_NEWBUSINESS = 'newbusiness'


def get_hubspot_endpoint_url(endpoint):
    return '{}{}'.format(HUBSPOT_API_BASE_URL, endpoint)


def get_authed_hubspot_endpoint_url(endpoint, api_key):
    return '{}?hapikey={}'.format(get_hubspot_endpoint_url(endpoint), api_key)


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


def get_hubspot_contact_vid(email):
    response = create_hubspot_contact(email)
    if 'vid' in response:
        return response['vid']
    return


def create_hubspot_deal_property(name, label, description, group_name, deal_type, field_type, trials=0):
    r = requests.post(
        get_authed_hubspot_endpoint_url(
            HUBSPOT_ENDPOINT_CREATE_DEAL_PROPERTY, HUBSPOT_API_KEY
        ),
        json={
            KEY_NAME: name,
            KEY_LABEL: label,
            KEY_DESCRIPTION: description,
            KEY_GROUPNAME: group_name,
            KEY_TYPE: deal_type,
            KEY_FIELDTYPE: field_type
        }
    )

    if r.status_code in [200, 201]:
        return r.json()
    return None


def create_hubspot_deal(task, trials=0):
    properties = []
    associatedVids = []

    client_vid = get_hubspot_contact_vid(task.user.email)
    associatedVids.append(client_vid)

    properties.extend(
        [
            dict(
                name=KEY_DEALNAME,
                value=task.summary
            ),
            dict(
                name=KEY_DEALSTAGE,
                value=KEY_VALUE_APPOINTMENT_SCHEDULED
            ),
            dict(
                name=KEY_PIPELINE,
                value=KEY_VALUE_DEFAULT
            ),
            dict(
                name=KEY_DEALTYPE,
                value=KEY_VALUE_NEWBUSINESS
            )
        ]
    )
    if task.pay:
        properties.append(
            dict(
                name=KEY_AMOUNT,
                value=str(task.pay)
            )
        )

    payload = dict(
        associations=dict(
            associatedCompanyIds=[],
            associatedVids=associatedVids
        ),
        properties=properties
    )

    r = requests.post(
        get_authed_hubspot_endpoint_url(
            HUBSPOT_ENDPOINT_CREATE_DEAL, HUBSPOT_API_KEY
        ), json=payload
    )
    print('deal', r)
    if r.status_code in [200, 201]:
        response = r.json()
        return response
    elif r.status_code >= 300 and trials < 1:
        if create_hubspot_deal_property(
                name='dealurl', label='Deal URL', description='URL of the deal',
                group_name='dealinformation', deal_type='string', field_type='text'
        ):
            return create_hubspot_deal(task, trials=trials+1)
    return None


def create_hubspot_engagement(from_email, to_emails, subject, body, **kwargs):
    contact_vids = []
    for email in to_emails:
        vid = get_hubspot_contact_vid(email)
        if vid:
            contact_vids.append(vid)

    alternatives = kwargs.get('alternatives', ())

    payload = {
        "engagement": {
            "active": True,
            "type": "EMAIL"
        },
        "associations": {
            "contactIds": contact_vids,
            "companyIds": [],
            "dealIds": kwargs.get('deal_ids', []) or []
        },
        "metadata": {
            "from": {
                "email": from_email,
                "firstName": "Tunga", "lastName": "Support"
            },
            "to": [{"email": email} for email in to_emails],
            "cc": [{"email": email} for email in kwargs.get('cc', []) or []],
            "bcc": [{"email": email} for email in kwargs.get('bcc', []) or []],
            "subject": subject,
            "html": alternatives and alternatives[0] or "",
            "text": body
        }
    }
    r = requests.post(
        get_authed_hubspot_endpoint_url(
            HUBSPOT_ENDPOINT_CREATE_ENGAGEMENT, HUBSPOT_API_KEY
        ), json=payload
    )

    print('engagement', r)
    if r.status_code in [200, 201]:
        response = r.json()
        return response
    return
