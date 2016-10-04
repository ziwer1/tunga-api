import re

from allauth.socialaccount.models import SocialToken
from decimal import Decimal, ROUND_UP
from django.http import HttpResponseRedirect
from django.utils.html import strip_tags

from tunga.settings import SOCIAL_CONNECT_USER_TYPE, SOCIAL_CONNECT_TASK
from tunga_profiles.models import AppIntegration
from tunga_utils.constants import USER_TYPE_DEVELOPER, USER_TYPE_PROJECT_OWNER


def clean_instance(instance, model):
    if instance and model:
        if isinstance(instance, model):
            return instance
        else:
            try:
                return model.objects.get(id=instance)
            except:
                return None
    else:
        return None


def pdf_base64encode(pdf_filename):
    return open(pdf_filename, "rb").read().encode("base64")


def swagger_permission_denied_handler(request):
    return HttpResponseRedirect('%s://%s/api/login/?next=/api/docs/' % (request.scheme, request.get_host()))


class Echo(object):
    """An object that implements just the write method of the file-like
    interface.
    """
    def write(self, value):
        """Write the value by returning it, instead of storing in a buffer."""
        return value


class GenericObject:
    def __init__(self, **kwargs):
        for k, v in kwargs.iteritems():
            setattr(self, k, v)


def get_session_user_type(request):
    try:
        user_type = int(request.session.get(SOCIAL_CONNECT_USER_TYPE, None))
    except:
        user_type = None
    if user_type in [USER_TYPE_DEVELOPER, USER_TYPE_PROJECT_OWNER]:
        return user_type
    return None


def get_session_task(request):
    try:
        return int(request.session.get(SOCIAL_CONNECT_TASK, None))
    except:
        return None


def get_social_token(user, provider):
    try:
        return SocialToken.objects.filter(account__user=user, account__provider=provider).latest('expires_at')
    except SocialToken.DoesNotExist:
        return None


def get_app_integration(user, provider):
    try:
        return AppIntegration.objects.filter(user=user, provider=provider).latest('updated_at')
    except AppIntegration.DoesNotExist:
        return None


def convert_to_text(body):
    return strip_tags(re.sub(r'<br\s*/>', '\n', body, flags=re.IGNORECASE))


def convert_to_html(body):
    return re.sub(r'(<br\s*/>)?\n', '<br/>', body, flags=re.IGNORECASE)


def round_decimal(number, ndigits):
    formatter = '{0:.%sf}' % ndigits
    return Decimal(formatter.format(Decimal(number)))
