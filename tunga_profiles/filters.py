from tunga_profiles.models import Education, Work, Connection, DeveloperApplication
from tunga_utils.filters import GenericDateFilterSet


class EducationFilter(GenericDateFilterSet):
    class Meta:
        model = Education
        fields = ('institution', 'award')


class WorkFilter(GenericDateFilterSet):
    class Meta:
        model = Work
        fields = ('company', 'position')


class ConnectionFilter(GenericDateFilterSet):
    class Meta:
        model = Connection
        fields = ('from_user', 'to_user', 'accepted', 'responded')


class DeveloperApplicationFilter(GenericDateFilterSet):
    class Meta:
        model = DeveloperApplication
        fields = ('status',)

