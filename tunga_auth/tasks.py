from django.contrib.auth import get_user_model
from django_rq.decorators import job

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
                address='{} {}'.format(user.profile.plot_number, user.profile.street),
                zip=user.profile.postal_code,
                company=user.profile.company,
                website=user.profile.website,
                phone=user.profile.phone_number
            )
        create_hubspot_contact(user.email, firstname=user.first_name, lastname=user.last_name, **profile_kwargs)
