from django.contrib.auth import get_user_model
from django_rq.decorators import job

from tunga.settings import MAILCHIMP_NEW_USER_AUTOMATION_WORKFLOW_ID, MAILCHIMP_NEW_USER_AUTOMATION_EMAIL_ID, \
    HUBSPOT_DOMIECK_OWNER_ID
from tunga_utils import mailchimp_utils
from tunga_utils.constants import USER_TYPE_PROJECT_OWNER
from tunga_utils.helpers import clean_instance
from tunga_utils.hubspot_utils import create_hubspot_contact


@job
def sync_hubspot_contact(user):
    user = clean_instance(user, get_user_model())
    if user.type == USER_TYPE_PROJECT_OWNER and not (user.is_staff and user.is_superuser):
        profile_kwargs = dict()
        if user.profile:
            profile_kwargs = dict(
                country=user.profile.country_name,
                city=user.profile.city_name,
                address='{} {}'.format(
                    user.profile.plot_number and user.profile.plot_number.encode('utf-8') or '',
                    user.profile.street and user.profile.street.encode('utf-8') or ''
                ),
                zip=user.profile.postal_code,
                company=user.profile.company,
                website=user.profile.website,
                phone=user.profile.phone_number,
                lifecyclestage='opportunity',
                hubspot_owner_id=HUBSPOT_DOMIECK_OWNER_ID
            )
        if user.source in ['wizard']:
            profile_kwargs.update({'tag': 'wizard call'})
        create_hubspot_contact(user.email, firstname=user.first_name, lastname=user.last_name, **profile_kwargs)


@job
def sync_hubspot_email(email):
    create_hubspot_contact(email)


@job
def subscribe_new_user_to_mailing_list(user):
    user = clean_instance(user, get_user_model())
    mailchimp_utils.subscribe_new_user(user.email, **dict(FNAME=user.first_name, LNAME=user.last_name))


@job
def trigger_schedule_call_automation(user):
    user = clean_instance(user, get_user_model())
    mailchimp_utils.add_email_to_automation_queue(
        email_address=user.email,
        workflow_id=MAILCHIMP_NEW_USER_AUTOMATION_WORKFLOW_ID,
        email_id=MAILCHIMP_NEW_USER_AUTOMATION_EMAIL_ID
    )
