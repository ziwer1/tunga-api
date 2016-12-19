from tunga.settings import SOCIAL_CONNECT_USER_TYPE, SOCIAL_CONNECT_TASK
from tunga_utils.constants import SESSION_VISITOR_EMAIL, USER_TYPE_DEVELOPER, USER_TYPE_PROJECT_OWNER


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