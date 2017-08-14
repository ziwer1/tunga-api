import json
import re

import datetime
from urllib import quote_plus, urlencode

import requests
from allauth.socialaccount.providers.facebook.provider import FacebookProvider
from allauth.socialaccount.providers.github.provider import GitHubProvider
from allauth.socialaccount.providers.google.provider import GoogleProvider
from allauth.socialaccount.providers.slack.provider import SlackProvider
from django.contrib.auth import get_user_model
from django.core.urlresolvers import reverse
from django.http.response import HttpResponse
from django.shortcuts import redirect
from django.template.loader import render_to_string
from dry_rest_permissions.generics import DRYPermissions
from rest_framework import views, status, generics, viewsets
from rest_framework.decorators import detail_route
from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.renderers import StaticHTMLRenderer
from rest_framework.response import Response
from weasyprint import HTML

from tunga.settings import GITHUB_SCOPES, COINBASE_CLIENT_ID, COINBASE_CLIENT_SECRET, SOCIAL_CONNECT_ACTION, SOCIAL_CONNECT_NEXT, SOCIAL_CONNECT_USER_TYPE, SOCIAL_CONNECT_ACTION_REGISTER, \
    SOCIAL_CONNECT_ACTION_CONNECT, SLACK_CLIENT_ID, SLACK_CLIENT_SECRET, SOCIAL_CONNECT_TASK, HARVEST_CLIENT_ID, \
    HARVEST_CLIENT_SECRET, SOCIAL_CONNECT_CALLBACK
from tunga_auth.filterbackends import UserFilterBackend
from tunga_auth.filters import UserFilter
from tunga_auth.models import EmailVisitor
from tunga_auth.permissions import IsAuthenticatedOrEmailVisitorReadOnly
from tunga_auth.serializers import UserSerializer, AccountInfoSerializer, EmailVisitorSerializer
from tunga_profiles.models import BTCWallet, UserProfile, AppIntegration
from tunga_tasks.renderers import PDFRenderer
from tunga_tasks.utils import save_task_integration_meta
from tunga_utils import coinbase_utils, slack_utils, harvest_utils
from tunga_utils.constants import BTC_WALLET_PROVIDER_COINBASE, PAYMENT_METHOD_BTC_WALLET, USER_TYPE_DEVELOPER, \
    USER_TYPE_PROJECT_OWNER, APP_INTEGRATION_PROVIDER_SLACK, APP_INTEGRATION_PROVIDER_HARVEST
from tunga_utils.filterbackends import DEFAULT_FILTER_BACKENDS
from tunga_auth.utils import get_session_task, get_session_visitor_email, create_email_visitor_session, get_session_next_url
from tunga_utils.helpers import get_social_token
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
    permission_classes = [DRYPermissions]

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
    permission_classes = [DRYPermissions]
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

    def get_serializer_class(self):
        if self.request.GET.get('simple', False):
            return SimpleUserSerializer
        return self.serializer_class

    @detail_route(
        methods=['get'], url_path='download/profile',
        renderer_classes=[PDFRenderer, StaticHTMLRenderer],
        permission_classes=[AllowAny]
    )
    def download_profile(self, request, user_id=None):
        """
        Download User Profile Endpoint
        ---
        omit_serializer: True
        omit_parameters:
            - query
        """
        current_url = '%s?%s' % (
            reverse(request.resolver_match.url_name, kwargs={'user_id': user_id}),
            urlencode(request.query_params)
        )
        login_url = '/signin?next=%s' % quote_plus(current_url)
        if not request.user.is_authenticated():
            return redirect(login_url)

        user = get_object_or_404(self.get_queryset(), pk=user_id)

        try:
            self.check_object_permissions(request, user)
        except NotAuthenticated:
            return redirect(login_url)
        except PermissionDenied:
            return HttpResponse("You do not have permission to access this estimate")

        ctx = {
            'user': user,
            'profile': user.profile,
            'work': user.work_set.all(),
            'education': user.education_set.all()
        }

        rendered_html = render_to_string("tunga/pdf/profile.html", context=ctx).encode(encoding="UTF-8")

        if request.accepted_renderer.format == 'html':
            return HttpResponse(rendered_html)

        pdf_file = HTML(string=rendered_html, encoding='utf-8').write_pdf()
        http_response = HttpResponse(pdf_file, content_type='application/pdf')
        http_response['Content-Disposition'] = 'filename="developer_profile.pdf"'
        return http_response


class EmailVisitorView(generics.CreateAPIView, generics.RetrieveAPIView):
    """
    Email Visitor resource.
    Manages sessions for email only visitors
    """
    queryset = EmailVisitor.objects.all()
    serializer_class = EmailVisitorSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        email = get_session_visitor_email(self.request)
        if email:
            try:
                # Visitor email logins will be valid for an hour
                return EmailVisitor.objects.get(email=email, last_login_at__gte=(datetime.datetime.utcnow() - datetime.timedelta(hours=1)))
            except:
                pass
        return None

    def retrieve(self, request, *args, **kwargs):
        visitor = self.get_object()
        if not visitor:
            return Response(
                {'status': 'Unauthorized', 'message': 'You are not an email visitor'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        serializer = self.get_serializer(instance=visitor)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = EmailVisitorSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        visitor = serializer.save()
        create_email_visitor_session(request, visitor.email)
        return Response(serializer.data)


def social_login_view(request, provider=None):
    action = request.GET.get(SOCIAL_CONNECT_ACTION)

    next_url = request.GET.get(SOCIAL_CONNECT_NEXT)
    if next_url:
        request.session[SOCIAL_CONNECT_NEXT] = next_url
    try:
        task = int(request.GET.get(SOCIAL_CONNECT_TASK))
    except:
        task = None

    if task:
        request.session[SOCIAL_CONNECT_TASK] = task

    if action == SOCIAL_CONNECT_ACTION_CONNECT or provider in [
        BTC_WALLET_PROVIDER_COINBASE,
        APP_INTEGRATION_PROVIDER_SLACK,
        APP_INTEGRATION_PROVIDER_HARVEST
    ]:

        if provider == BTC_WALLET_PROVIDER_COINBASE:
            redirect_uri = '%s://%s%s' % (request.scheme, request.get_host(), reverse('coinbase-connect-callback'))
            return redirect(coinbase_utils.get_authorize_url(redirect_uri))
        elif provider == APP_INTEGRATION_PROVIDER_SLACK:
            redirect_uri = '%s://%s%s' % (request.scheme, request.get_host(), reverse('slack-connect-callback'))
            return redirect(slack_utils.get_authorize_url(redirect_uri))
        if provider == APP_INTEGRATION_PROVIDER_HARVEST:
            redirect_uri = '%s://%s%s' % (request.scheme, request.get_host(), reverse('harvest-connect-callback'))
            return redirect(harvest_utils.get_authorize_url(redirect_uri))

    enabled_providers = [FacebookProvider.id, GoogleProvider.id, GitHubProvider.id, SlackProvider.id]

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
            redirect_uri = '%s://%s%s' % (request.scheme, request.get_host(), reverse('github-connect-callback'))
            if redirect_uri:
                request.session[SOCIAL_CONNECT_CALLBACK] = redirect_uri
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


def github_connect_callback(request):
    task_id = get_session_task(request)
    if task_id:
        social_token = get_social_token(user=request.user, provider=GitHubProvider.id)
        if not social_token:
            return Response({'status': 'Unauthorized'}, status.HTTP_401_UNAUTHORIZED)

        token_info = dict(
            token=social_token.token,
            token_secret=social_token.token_secret,
            token_expires_at=social_token.expires_at
        )

        save_task_integration_meta(task_id, GitHubProvider.id, token_info)

    return redirect(get_session_next_url(request, provider=GitHubProvider.id))


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

        task_id = get_session_task(request)
        if task_id:
            token_info = {
                'token': response['access_token'],
                'token_extra': json.dumps(response)
            }
            if 'bot' in response:
                token_info['bot_access_token'] = response['bot'].get('bot_access_token')
                token_info['bot_user_id'] = response['bot'].get('bot_user_id')
            save_task_integration_meta(task_id, APP_INTEGRATION_PROVIDER_SLACK, token_info)
    return redirect(get_session_next_url(request, provider=APP_INTEGRATION_PROVIDER_SLACK))


def harvest_connect_callback(request):
    code = request.GET.get('code', None)
    redirect_uri = '%s://%s%s' % (request.scheme, request.get_host(), reverse(request.resolver_match.url_name))
    r = requests.post(url=harvest_utils.get_token_url(), data={
        'code': code,
        'client_id': HARVEST_CLIENT_ID,
        'client_secret': HARVEST_CLIENT_SECRET,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code'
    })

    if r.status_code == 200:
        response = r.json()
        defaults = {
            'token': response['access_token'],
            'token_secret': response['refresh_token'],
            'extra': json.dumps(response)
        }
        AppIntegration.objects.update_or_create(
            user=request.user, provider=APP_INTEGRATION_PROVIDER_HARVEST, defaults=defaults
        )

        task_id = get_session_task(request)
        if task_id:
            token_info = {
                'token': response['access_token'],
                'refresh_token': response['refresh_token'],
                'token_extra': json.dumps(response)
            }
            save_task_integration_meta(task_id, APP_INTEGRATION_PROVIDER_HARVEST, token_info)

    return redirect(get_session_next_url(request, provider=APP_INTEGRATION_PROVIDER_HARVEST))
