import django_filters

from tunga_support.models import SupportSection, SupportPage
from tunga_utils.filters import GenericDateFilterSet


class SupportSectionFilter(GenericDateFilterSet):

    class Meta:
        model = SupportSection
        fields = ('visibility',)


class SupportPageFilter(GenericDateFilterSet):
    section = django_filters.CharFilter(name='section__slug')
    tag = django_filters.CharFilter(name='tags__slug')

    class Meta:
        model = SupportPage
        fields = ('visibility', 'section', 'tags')
