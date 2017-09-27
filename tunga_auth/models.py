# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.tokens import default_token_generator
from django.db import models
from django.utils.encoding import force_bytes, python_2_unicode_compatible
from django.utils.http import urlsafe_base64_encode
from dry_rest_permissions.generics import allow_staff_or_superuser

from tunga_utils import bitcoin_utils, coinbase_utils
from tunga_utils.constants import PAYMENT_METHOD_BTC_ADDRESS, PAYMENT_METHOD_BTC_WALLET, BTC_WALLET_PROVIDER_COINBASE, \
    USER_TYPE_DEVELOPER, USER_TYPE_PROJECT_OWNER, USER_TYPE_PROJECT_MANAGER, USER_SOURCE_DEFAULT, \
    USER_SOURCE_TASK_WIZARD

USER_TYPE_CHOICES = (
    (USER_TYPE_DEVELOPER, 'Developer'),
    (USER_TYPE_PROJECT_OWNER, 'Project Owner'),
    (USER_TYPE_PROJECT_MANAGER, 'Project Manager')
)

USER_SOURCE_CHOICES = (
    (USER_SOURCE_DEFAULT, 'Default'),
    (USER_SOURCE_TASK_WIZARD, 'Task Wizard')
)


class TungaUser(AbstractUser):
    type = models.IntegerField(choices=USER_TYPE_CHOICES, blank=True, null=True)
    image = models.ImageField(upload_to='photos/%Y/%m/%d', blank=True, null=True)
    verified = models.BooleanField(default=False)
    pending = models.BooleanField(default=True)
    source = models.IntegerField(choices=USER_SOURCE_CHOICES, default=USER_SOURCE_DEFAULT)
    last_activity_at = models.DateTimeField(blank=True, null=True)
    last_set_password_email_at = models.DateTimeField(blank=True, null=True)

    class Meta(AbstractUser.Meta):
        unique_together = ('email',)

    def save(self, *args, **kwargs):
        if self.type == USER_TYPE_PROJECT_OWNER:
            self.pending = False
        super(TungaUser, self).save(*args, **kwargs)

    def __str__(self):
        return '{} ({})'.format(self.display_name, self.get_username())

    @staticmethod
    @allow_staff_or_superuser
    def has_read_permission(request):
        return True

    @allow_staff_or_superuser
    def has_object_read_permission(self, request):
        return True

    @staticmethod
    @allow_staff_or_superuser
    def has_write_permission(request):
        return request.user.is_authenticated()

    @allow_staff_or_superuser
    def has_object_write_permission(self, request):
        return request.user.is_authenticated() and request.user.id == self.id

    @property
    def display_name(self):
        return (self.get_full_name() or self.username).title()

    @property
    def short_name(self):
        return (self.get_short_name() or self.username).title()

    @property
    def name(self):
        return (self.get_full_name() or self.username).title()

    @property
    def display_type(self):
        return self.get_type_display()

    @property
    def is_admin(self):
        return self.is_staff or self.is_superuser

    @property
    def is_developer(self):
        return self.type == USER_TYPE_DEVELOPER

    @property
    def is_project_owner(self):
        return self.type == USER_TYPE_PROJECT_OWNER

    @property
    def is_project_manager(self):
        return self.type == USER_TYPE_PROJECT_MANAGER

    @property
    def avatar_url(self):
        if self.image:
            return self.image.url
        social_accounts = self.socialaccount_set.all()
        if social_accounts:
            return social_accounts[0].get_avatar_url()
        return None

    @property
    def profile(self):
        try:
            return self.userprofile
        except:
            return None

    @property
    def payment_method(self):
        if not self.profile:
            return None
        return self.profile.payment_method

    @property
    def mobile_money_cc(self):
        if not self.profile:
            return None
        return self.profile.mobile_money_cc

    @property
    def mobile_money_number(self):
        if not self.profile:
            return None
        return self.profile.mobile_money_number

    @property
    def btc_address(self):
        if not self.profile:
            return None

        if self.profile.payment_method == PAYMENT_METHOD_BTC_ADDRESS:
            if bitcoin_utils.is_valid_btc_address(self.profile.btc_address):
                return self.profile.btc_address
        elif self.profile.payment_method == PAYMENT_METHOD_BTC_WALLET:
            wallet = self.profile.btc_wallet
            if wallet.provider == BTC_WALLET_PROVIDER_COINBASE:
                client = coinbase_utils.get_oauth_client(wallet.token, wallet.token_secret, self)
                return coinbase_utils.get_new_address(client)
        return None

    @property
    def is_confirmed(self):
        return self.emailaddress_set.filter(verified=True).count() > 0

    @property
    def uid(self):
        return urlsafe_base64_encode(force_bytes(self.pk))

    def generate_reset_token(self):
        return default_token_generator.make_token(self)

    @property
    def tax_rate(self):
        if self.profile and self.profile.country and self.profile.country.code == 'NL':
            return 21
        return 0


@python_2_unicode_compatible
class EmailVisitor(models.Model):
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.email

    class Meta:
        ordering = ['-created_at']
