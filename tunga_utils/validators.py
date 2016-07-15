import datetime
import re

from django.core.exceptions import ValidationError

from tunga_utils.bitcoin_utils import is_valid_btc_address


def validate_year(value):
    this_year = datetime.date.today().year
    min_year = this_year - 80
    if value < min_year:
        raise ValidationError('Year should be after %s' % min_year)
    if value > this_year:
        raise ValidationError('Year should not be after %s' % this_year)


def validate_btc_address(value):
    error_msg = 'Invalid Bitcoin address.'
    if re.match(r"[a-zA-Z1-9]{27,35}$", value) is None:
        raise ValidationError(error_msg)
    if not is_valid_btc_address(value):
        raise ValidationError(error_msg)
