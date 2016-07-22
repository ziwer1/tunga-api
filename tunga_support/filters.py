from tunga_support.models import SupportSection, SupportPage
from tunga_utils.filters import GenericDateFilterSet


class SupportSectionFilter(GenericDateFilterSet):

    class Meta:
        model = SupportSection
        fields = ('visibility',)


class SupportPageFilter(GenericDateFilterSet):

    class Meta:
        model = SupportPage
        fields = ('visibility', 'section')
