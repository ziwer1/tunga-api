from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from rest_framework import views, status, generics, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from tunga_auth.filterbackends import UserFilterBackend
from tunga_auth.filters import UserFilter
from tunga_auth.models import USER_TYPE_DEVELOPER, USER_TYPE_PROJECT_OWNER
from tunga_auth.serializers import UserSerializer, AccountInfoSerializer
from tunga_utils.serializers import SimpleUserSerializer
from tunga_utils.filterbackends import DEFAULT_FILTER_BACKENDS


class VerifyUserView(views.APIView):
    """
    Verifies Current user.
    Returns user object if user is logged in, otherwise 401 Unauthorized
    """
    permission_classes = [IsAuthenticated]

    def get_object(self, request):
        user = request.user
        if user is not None and user.is_authenticated():
            return user
        else:
            return None

    def get(self, request):
        user = self.get_object(request)
        if user is None:
            return Response(
                {'status': 'Unauthorized', 'message': 'You are not logged in'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        serializer = SimpleUserSerializer(user)
        return Response(serializer.data)


class AccountInfoView(generics.RetrieveUpdateAPIView):
    """
    Account Info Resource
    Manage current user's account info
    """
    queryset = get_user_model().objects.all()
    serializer_class = AccountInfoSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        user = self.request.user
        if user is not None and user.is_authenticated():
            return user
        else:
            return None


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    User Resource
    """
    queryset = get_user_model().objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    filter_class = UserFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (UserFilterBackend,)
    search_fields = ('^username', '^first_name', '^last_name', '=email', 'userprofile__skills__name')


def social_login_view(request, provider=None):
    enabled_providers = ['facebook', 'google', 'github']
    action = request.GET.get('action')
    try:
        user_type = int(request.GET.get('user_type'))
    except:
        user_type = None
    if action == 'register':
        if user_type in [USER_TYPE_DEVELOPER, USER_TYPE_PROJECT_OWNER]:
            request.session['user_type'] = user_type
        else:
            return redirect('/signup/')

    if provider in enabled_providers:
        next_url = '/accounts/%s/login/' % provider
    else:
        next_url = '/'
    return redirect(next_url)
