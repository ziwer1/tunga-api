import re

import requests
from django.contrib.auth import get_user_model
from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from rest_framework import views, status, generics, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from tunga.settings import GITHUB_SCOPES, COINBASE_CLIENT_ID, COINBASE_CLIENT_SECRET
from tunga_auth.filterbackends import UserFilterBackend
from tunga_auth.filters import UserFilter
from tunga_auth.models import USER_TYPE_DEVELOPER, USER_TYPE_PROJECT_OWNER
from tunga_auth.serializers import UserSerializer, AccountInfoSerializer
from tunga_profiles.models import BTC_WALLET_PROVIDER_COINBASE, BTCWallet, UserProfile, PAYMENT_METHOD_BTC_WALLET
from tunga_utils import coinbase_utils
from tunga_utils.filterbackends import DEFAULT_FILTER_BACKENDS
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
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = 'user_id'
    lookup_field = 'id'
    filter_class = UserFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (UserFilterBackend,)
    search_fields = ('^username', '^first_name', '^last_name', '=email', 'userprofile__skills__name')

    def get_object(self):
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        id = self.kwargs[lookup_url_kwarg]
        if re.match(r'[^\d]', id):

            self.lookup_field = 'username'
        return super(UserViewSet, self).get_object()


def social_login_view(request, provider=None):
    if provider == BTC_WALLET_PROVIDER_COINBASE:
        redirect_uri = '%s://%s%s' % (request.scheme, request.get_host(), reverse('coinbase-connect-callback'))
        return redirect(coinbase_utils.get_authorize_url(redirect_uri))
    enabled_providers = ['facebook', 'google', 'github']
    action = request.GET.get('action')
    next = request.GET.get('next')
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
        if provider == 'github' and action == 'connect':
            scope = ','.join(GITHUB_SCOPES)
            next_url += '?scope=%s&process=connect' % scope
            if next:
                next_url += '&next=%s' % next
    else:
        next_url = '/'
    return redirect(next_url)


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
