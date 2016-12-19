import json
import re

import requests
from allauth.socialaccount.providers.facebook.provider import FacebookProvider
from allauth.socialaccount.providers.github.provider import GitHubProvider
from allauth.socialaccount.providers.google.provider import GoogleProvider
from allauth.socialaccount.providers.slack.provider import SlackProvider
from django.contrib.auth import get_user_model
from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from rest_framework import views, status, generics, viewsets
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from tunga.settings import GITHUB_SCOPES, COINBASE_CLIENT_ID, COINBASE_CLIENT_SECRET, SOCIAL_CONNECT_ACTION, SOCIAL_CONNECT_NEXT, SOCIAL_CONNECT_USER_TYPE, SOCIAL_CONNECT_ACTION_REGISTER, \
    SOCIAL_CONNECT_ACTION_CONNECT, SLACK_CLIENT_ID, SLACK_CLIENT_SECRET, SOCIAL_CONNECT_TASK
from tunga_auth.filterbackends import UserFilterBackend
from tunga_auth.filters import UserFilter
from tunga_auth.permissions import IsAuthenticatedOrEmailVisitorReadOnly
from tunga_auth.serializers import UserSerializer, AccountInfoSerializer, EmailVisitorSerializer
from tunga_profiles.models import BTCWallet, UserProfile, AppIntegration
from tunga_utils import coinbase_utils, slack_utils
from tunga_utils.constants import BTC_WALLET_PROVIDER_COINBASE, PAYMENT_METHOD_BTC_WALLET, USER_TYPE_DEVELOPER, \
    USER_TYPE_PROJECT_OWNER, APP_INTEGRATION_PROVIDER_SLACK
from tunga_utils.filterbackends import DEFAULT_FILTER_BACKENDS
from tunga_auth.utils import get_session_task, get_session_visitor_email, create_email_visitor_session
from tunga_utils.serializers import SimpleUserSerializer


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
    queryset = get_user_model().objects.order_by('first_name', 'last_name')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticatedOrEmailVisitorReadOnly]
    lookup_url_kwarg = 'user_id'
    lookup_field = 'id'
    lookup_value_regex = '[^/]+'
    filter_class = UserFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (UserFilterBackend,)
    search_fields = ('^username', '^first_name', '^last_name', '=email', 'userprofile__skills__name')

    def get_object(self):
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        user_id = self.kwargs[lookup_url_kwarg]
        if re.match(r'[^\d]', user_id):
            self.lookup_field = 'username'
        return super(UserViewSet, self).get_object()


class EmailVisitorView(views.APIView):
    """
    Email Visitor resource.
    Manages sessions for email only visitors
    ---
    GET:
        response_serializer: EmailVisitorSerializer
    POST:
        request_serializer: EmailVisitorSerializer
        response_serializer: EmailVisitorSerializer
    """
    permission_classes = [AllowAny]

    def get(self, request):
        email = get_session_visitor_email(request)
        if not email:
            return Response(
                {'status': 'Unauthorized', 'message': 'You are not an email visitor'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        return Response(dict(email=email))

    def post(self, request):
        serializer = EmailVisitorSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        create_email_visitor_session(request, serializer.data['email'])
        return Response(serializer.data)


def social_login_view(request, provider=None):
    action = request.GET.get(SOCIAL_CONNECT_ACTION)

    if action == SOCIAL_CONNECT_ACTION_CONNECT:
        if provider == BTC_WALLET_PROVIDER_COINBASE:
            redirect_uri = '%s://%s%s' % (request.scheme, request.get_host(), reverse('coinbase-connect-callback'))
            return redirect(coinbase_utils.get_authorize_url(redirect_uri))

        if provider == APP_INTEGRATION_PROVIDER_SLACK:
            try:
                task = int(request.GET.get(SOCIAL_CONNECT_TASK))
            except:
                task = None

            if task:
                request.session[SOCIAL_CONNECT_TASK] = task

            redirect_uri = '%s://%s%s' % (request.scheme, request.get_host(), reverse('slack-connect-callback'))
            return redirect(slack_utils.get_authorize_url(redirect_uri))

    enabled_providers = [FacebookProvider.id, GoogleProvider.id, GitHubProvider.id, SlackProvider.id]
    redirect_uri = request.GET.get(SOCIAL_CONNECT_NEXT)
    try:
        user_type = int(request.GET.get(SOCIAL_CONNECT_USER_TYPE))
    except:
        user_type = None

    if action == SOCIAL_CONNECT_ACTION_REGISTER:
        if user_type in [USER_TYPE_DEVELOPER, USER_TYPE_PROJECT_OWNER]:
            request.session[SOCIAL_CONNECT_USER_TYPE] = user_type
        else:
            return redirect('/signup/')

    if provider in enabled_providers:
        authorize_url = '/accounts/%s/login/' % provider
        if provider == GitHubProvider.id and action == SOCIAL_CONNECT_ACTION_CONNECT:
            scope = ','.join(GITHUB_SCOPES)
            authorize_url += '?scope=%s&process=connect' % scope
            if redirect_uri:
                authorize_url += '&next=%s' % redirect_uri
    else:
        authorize_url = '/'
    return redirect(authorize_url)


def coinbase_connect_callback(request):
    code = request.GET.get('code', None)
    redirect_uri = '%s://%s%s' % (request.scheme, request.get_host(), reverse(request.resolver_match.url_name))
    r = requests.post(url=coinbase_utils.get_token_url(), data={
        'grant_type': 'authorization_code',
        'code': code,
        'client_id': COINBASE_CLIENT_ID,
        'client_secret': COINBASE_CLIENT_SECRET,
        'redirect_uri': redirect_uri
    })

    if r.status_code == 200:
        response = r.json()
        defaults = {
            'token': response['access_token'],
            'token_secret': response['refresh_token'],
            # 'expires_at': response['expires_in'] # Coinbase returns an interval here
        }
        wallet, created = BTCWallet.objects.update_or_create(
            user=request.user, provider=BTC_WALLET_PROVIDER_COINBASE, defaults=defaults
        )
        UserProfile.objects.update_or_create(user=request.user, defaults={
            'payment_method': PAYMENT_METHOD_BTC_WALLET, 'btc_wallet': wallet
        })

    return redirect('/profile/payment/coinbase/')


def slack_connect_callback(request):
    code = request.GET.get('code', None)
    redirect_uri = '%s://%s%s' % (request.scheme, request.get_host(), reverse(request.resolver_match.url_name))
    r = requests.post(url=slack_utils.get_token_url(), data={
        'code': code,
        'client_id': SLACK_CLIENT_ID,
        'client_secret': SLACK_CLIENT_SECRET,
        'redirect_uri': redirect_uri
    })

    if r.status_code == 200:
        response = r.json()
        defaults = {
            'token': response['access_token'],
            'extra': json.dumps(response)
        }
        AppIntegration.objects.update_or_create(
            user=request.user, provider=APP_INTEGRATION_PROVIDER_SLACK, defaults=defaults
        )
    return redirect('/task/%s/integrations/slack' % get_session_task(request))
