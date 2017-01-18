from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.models import EmailAddress
from allauth.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.shortcuts import redirect

from tunga_utils.constants import USER_TYPE_DEVELOPER
from tunga_auth.utils import get_session_user_type, get_session_callback_url


class TungaAccountAdapter(DefaultAccountAdapter):
    pass


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        """
        Invoked just after a user successfully authenticates via a
        social provider, but before the login is actually processed
        (and before the pre_social_login signal is emitted).

        We're trying to solve different use cases:
        - social account already exists, just go on
        - social account has no email or email is unknown, just go on
        - social account's email exists, link social account to existing user
        """

        # Ignore existing social accounts, just do this stuff for new ones
        if sociallogin.is_existing:
            return

        # some social logins don't have an email address, e.g. facebook accounts
        # with mobile numbers only, but allauth takes care of this case so just
        # ignore it
        if 'email' not in sociallogin.account.extra_data:
            return

        if request.user.is_authenticated():
            return

        # check if given email address already exists.
        # Note: __iexact is used to ignore cases
        try:
            email = sociallogin.account.extra_data['email'].lower()
            email_address = EmailAddress.objects.get(email__iexact=email)

        # if it does not, let allauth take care of this new social account
        except EmailAddress.DoesNotExist:
            user_type = get_session_user_type(request)
            if not user_type:
                # User type is required
                raise ImmediateHttpResponse(redirect('/signup/'))
            elif user_type == USER_TYPE_DEVELOPER:
                # Developers need to be approved first
                raise ImmediateHttpResponse(redirect('/signup/developer/'))
            return

        # if it does, connect this new social login to the existing user
        user = email_address.user
        sociallogin.connect(request, user)

        # Consider a redirect to login with a message instead of an automatic connection
        # if it does, bounce back to the login page
        # account = get_user_model().objects.get(email=email).socialaccount_set.first()
        # messages.error(request, "A "+account.provider.capitalize()+" account already exists associated to "+email_address.email+". Log in with that instead, and connect your "+sociallogin.account.provider.capitalize()+" account through your profile page to link them together.")
        # raise ImmediateHttpResponse(redirect('/accounts/login'))

    def populate_user(self, request, sociallogin, data):
        user = super(SocialAccountAdapter, self).populate_user(request, sociallogin, data)
        if not sociallogin.is_existing:
            # Read the user type from session if provided for new users
            user_type = get_session_user_type(request)
            user.type = user_type
        return user

    def get_connect_redirect_url(self, request, socialaccount):
        assert request.user.is_authenticated()
        callback = get_session_callback_url(request)
        if callback:
            return callback
        return super(SocialAccountAdapter, self).get_connect_redirect_url(request, socialaccount)
