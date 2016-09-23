from allauth.socialaccount.models import SocialToken
from django.http.response import HttpResponseRedirect
from rest_framework import viewsets, generics
from rest_framework.permissions import IsAuthenticated, AllowAny

from tunga_profiles.models import Skill
from tunga_utils.constants import USER_TYPE_DEVELOPER, USER_TYPE_PROJECT_OWNER
from tunga_utils.models import ContactRequest
from tunga_utils.serializers import SkillSerializer, ContactRequestSerializer


class SkillViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Skills Resource
    """
    queryset = Skill.objects.all()
    serializer_class = SkillSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ('name', )


class ContactRequestView(generics.CreateAPIView):
    """
    Contact Request Resource
    """
    queryset = ContactRequest.objects.all()
    serializer_class = ContactRequestSerializer
    permission_classes = [AllowAny]


def swagger_permission_denied_handler(request):
    return HttpResponseRedirect('%s://%s/api/login/?next=/api/docs/' % (request.scheme, request.get_host()))


class Echo(object):
    """An object that implements just the write method of the file-like
    interface.
    """
    def write(self, value):
        """Write the value by returning it, instead of storing in a buffer."""
        return value


def get_session_user_type(request):
    try:
        user_type = int(request.session.get('user_type', None))
    except:
        user_type = None
    if user_type in [USER_TYPE_DEVELOPER, USER_TYPE_PROJECT_OWNER]:
        return user_type
    return None


def get_social_token(user, provider):
    try:
        return SocialToken.objects.filter(account__user=user, account__provider=provider).latest('expires_at')
    except SocialToken.DoesNotExist:
        return None
