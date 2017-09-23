import django_filters
from django.contrib.auth import get_user_model

from tunga_utils.filters import NumberInFilter


class UserFilter(django_filters.FilterSet):
    skill = django_filters.CharFilter(name='userprofile__skills__name', label='skills')
    skill_id = django_filters.NumberFilter(name='userprofile__skills', label='skills (by ID)')
    types = NumberInFilter(name='type', lookup_expr='in', label='types')

    class Meta:
        model = get_user_model()
        fields = ('type', 'skill', 'skill_id', 'types')
