from django.contrib.auth.apps import AuthConfig
from django.utils.translation import ugettext_lazy as _


class DjangoAuthConfig(AuthConfig):
    verbose_name = _("Authorization")
