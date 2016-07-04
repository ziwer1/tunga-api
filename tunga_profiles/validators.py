from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError


def validate_email(value):
    if get_user_model().objects.filter(email__iexact=value).count():
        raise ValidationError('This email is already associated with a Tunga account')
