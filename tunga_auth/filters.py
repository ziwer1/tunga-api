import django_filters
from django.contrib.auth import get_user_model


class UserFilter(django_filters.FilterSet):
    skills = django_filters.MethodFilter(label='Skills (Name)')
    skills_id = django_filters.NumberFilter(name='userprofile__skills', label='Skills (ID)')

    class Meta:
        model = get_user_model()
        fields = ('type', 'skills', 'skills_id')

    def filter_skills(self, queryset, value):
        return queryset


