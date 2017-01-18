from allauth.socialaccount.providers.github.provider import GitHubProvider

from tunga.settings import SOCIAL_CONNECT_USER_TYPE, SOCIAL_CONNECT_TASK, SOCIAL_CONNECT_CALLBACK, SOCIAL_CONNECT_NEXT
from tunga_utils.constants import SESSION_VISITOR_EMAIL, USER_TYPE_DEVELOPER, USER_TYPE_PROJECT_OWNER, \
    APP_INTEGRATION_PROVIDER_SLACK, APP_INTEGRATION_PROVIDER_HARVEST


def create_email_visitor_session(request, email):
    request.session[SESSION_VISITOR_EMAIL] = email


def get_session_visitor_email(request):
    return request.session.get(SESSION_VISITOR_EMAIL, None)


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


def get_session_next_url(request, provider=None):
    try:
        next_url = request.session.get(SOCIAL_CONNECT_NEXT, None)
    except:
        next_url = None
    if next_url:
        return next_url

    task_id = get_session_task(request)
    if task_id:
        provider_name = None
        if provider == GitHubProvider.id:
            provider_name = 'github'
        elif provider == APP_INTEGRATION_PROVIDER_SLACK:
            provider_name = 'slack'
        elif provider == APP_INTEGRATION_PROVIDER_HARVEST:
            provider_name = 'harvest'
        return '/task/%s/integrations/%s' % (task_id, provider_name)
    return '/'


def get_session_callback_url(request):
    try:
        return request.session.get(SOCIAL_CONNECT_CALLBACK, None)
    except:
        return None


def get_request_task(request):
    try:
        return int(request.GET.get(SOCIAL_CONNECT_TASK))
    except:
        return None
