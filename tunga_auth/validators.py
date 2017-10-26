import re

from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _


class PasswordStrengthValidator(object):
    """
    Validate password strength.
    """
    def validate(self, password, user=None):
        if not re.search(r'\d', password):
            raise ValidationError(
                _("This password does not contain any numbers."),
                code='password_too_weak',
            )
        if not re.search(r'[^\d]', password):
            raise ValidationError(
                _("This password does not contain any alphabetic characters."),
                code='password_too_weak',
            )

    def get_help_text(self):
        return _("Your password must contain both numeric and alphabetic characters.")