import datetime
from django.core.exceptions import ValidationError


def validate_year(value):
    this_year = datetime.date.today().year
    min_year = this_year - 80
    if value < min_year:
        raise ValidationError('Year should be after %s' % min_year)
    if value > this_year:
        raise ValidationError('Year should not be after %s' % this_year)
