import django_filters
from django.contrib.auth import get_user_model


class UserFilter(django_filters.FilterSet):
    skill = django_filters.CharFilter(name='userprofile__skills__name', label='skills')
    skill_id = django_filters.NumberFilter(name='userprofile__skills', label='skills (by ID)')

    class Meta:
        model = get_user_model()
        fields = ('type', 'skill', 'skill_id')
