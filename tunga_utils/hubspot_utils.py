import requests
from django.utils import six

from tunga.settings import HUBSPOT_API_KEY, TUNGA_URL, HUBSPOT_DEFAULT_DEAL_STAGE_MEMBER, HUBSPOT_DEFAULT_DEAL_STAGE_NEW_USER
from tunga_utils.constants import TASK_SOURCE_NEW_USER

HUBSPOT_API_BASE_URL = 'https://api.hubapi.com'
HUBSPOT_ENDPOINT_CREATE_UPDATE_CONTACT = '/contacts/v1/contact/createOrUpdate/email/{contact_email}/'
HUBSPOT_ENDPOINT_CREATE_DEAL = '/deals/v1/deal'
HUBSPOT_ENDPOINT_CREATE_DEAL_PROPERTY = '/properties/v1/deals/properties/'
HUBSPOT_ENDPOINT_CREATE_TAG_PROPERTY = '/contacts/v1/properties/tag'
HUBSPOT_ENDPOINT_CREATE_ENGAGEMENT = '/engagements/v1/engagements'
HUBSPOT_ENDPOINT_GET_OWNER = '/owners/v2/owners'

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

KEY_DEALURL = 'dealurl'
KEY_SCHEDULE_CALL_START = 'schedulecallstart'
KEY_SCHEDULE_CALL_END = 'schedulecallend'

KEY_VALUE_DEFAULT = 'default'
KEY_VALUE_NEWBUSINESS = 'newbusiness'
KEY_VALUE_EXISTINGBUSINESS = 'existingbusiness'
KEY_VALUE_APPOINTMENT_SCHEDULED = 'appointmentscheduled'
KEY_VALUE_QUALIFIEDTOBUY = 'qualifiedtobuy'
KEY_VALUE_PRESENTATION_SCHEDULED = 'presentationscheduled'
KEY_VALUE_DECISION_MAKER_BOUGHTIN = 'decisionmakerboughtin'
KEY_VALUE_CONTRACT_SENT = 'contractsent'
KEY_VALUE_CLOSED_WON = 'closedwon'
KEY_VALUE_CLOSED_LOST = 'closedlost'


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


def create_hubspot_deal_property(name, label, description, group_name, property_type, field_type, trials=0):
    r = requests.post(
        get_authed_hubspot_endpoint_url(
            HUBSPOT_ENDPOINT_CREATE_DEAL_PROPERTY, HUBSPOT_API_KEY
        ),
        json={
            KEY_NAME: name,
            KEY_LABEL: label,
            KEY_DESCRIPTION: description,
            KEY_GROUPNAME: group_name,
            KEY_TYPE: property_type,
            KEY_FIELDTYPE: field_type
        }
    )

    if r.status_code in [200, 201]:
        return r.json()
    return None


def create_or_update_hubspot_deal(task, trials=0, **kwargs):
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
                name=KEY_DEALURL,
                value='{}/{}'.format(TUNGA_URL, task.id)
            )
        ]
    )

    if not task.hubspot_deal_id:
        properties.extend(
            [
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

    if KEY_DEALSTAGE in kwargs or not task.hubspot_deal_id:
        deal_stage = kwargs.get(
            KEY_DEALSTAGE,
            task.source == TASK_SOURCE_NEW_USER and HUBSPOT_DEFAULT_DEAL_STAGE_NEW_USER or HUBSPOT_DEFAULT_DEAL_STAGE_MEMBER
        )
        properties.append(
            dict(
                name=KEY_DEALSTAGE,
                value=deal_stage or KEY_VALUE_APPOINTMENT_SCHEDULED
            )
        )

    if task.pay:
        properties.append(
            dict(
                name=KEY_AMOUNT,
                value=str(task.pay)
            )
        )
    if task.schedule_call_start:
        properties.append(
            dict(
                name=KEY_SCHEDULE_CALL_START,
                value=task.schedule_call_start.isoformat()
            )
        )
    if task.schedule_call_end:
        properties.append(
            dict(
                name=KEY_SCHEDULE_CALL_END,
                value=task.schedule_call_end.isoformat()
            )
        )
    if 'createdate' in kwargs:
        properties.append(
            dict(
                name='createdate',
                value=kwargs['createdate']
            )
        )

    payload = dict(
        associations=dict(
            associatedCompanyIds=[],
            associatedVids=associatedVids
        ),
        properties=properties
    )

    if task.hubspot_deal_id:
        r = requests.put(
            get_authed_hubspot_endpoint_url(
                '{}/{}'.format(HUBSPOT_ENDPOINT_CREATE_DEAL, task.hubspot_deal_id), HUBSPOT_API_KEY
            ), json=payload
        )
    else:
        r = requests.post(
            get_authed_hubspot_endpoint_url(
                HUBSPOT_ENDPOINT_CREATE_DEAL, HUBSPOT_API_KEY
            ), json=payload
        )

    if r.status_code in [200, 201]:
        response = r.json()
        task.hubspot_deal_id = response['dealId']
        task.save()
        return response
    elif r.status_code >= 300 and trials < 3:
        # Create properties
        create_hubspot_deal_property(
            name=KEY_DEALURL, label='Deal URL', description='URL of the deal',
            group_name='dealinformation', property_type='string', field_type='text'
        )
        create_hubspot_deal_property(
            name=KEY_SCHEDULE_CALL_START, label='Availability Window Starts',
            description='Start of availability window',
            group_name='dealinformation', property_type='datetime', field_type='date'
        )
        create_hubspot_deal_property(
            name=KEY_SCHEDULE_CALL_END, label='Availability Window Ends',
            description='End of availability window',
            group_name='dealinformation', property_type='datetime', field_type='date'
        )
        # Try again
        return create_or_update_hubspot_deal(task, trials=trials + 1)
    return None


def create_hubspot_engagement(from_email, to_emails, subject, body, **kwargs):
    contact_vids = []
    for email in to_emails:
        vid = get_hubspot_contact_vid(email)
        if vid:
            contact_vids.append(vid)

    alternatives = kwargs.get('alternatives', ())
    deal_ids = []
    for deal_id in kwargs.get('deal_ids', []) or []:
        if deal_id:
            deal_ids.append(deal_id)

    payload = {
        "engagement": {
            "active": True,
            "type": "EMAIL"
        },
        "associations": {
            "contactIds": contact_vids,
            "companyIds": [],
            "dealIds": deal_ids
        },
        "metadata": {
            "from": {
                "email": from_email,
                "firstName": "Tunga"  # , "lastName": "Support"
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

    if r.status_code in [200, 201]:
        response = r.json()
        return response
    return
