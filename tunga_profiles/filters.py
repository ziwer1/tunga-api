from tunga_profiles.models import Education, Work, Connection, SocialLink
from tunga_utils.filters import GenericDateFilterSet


class SocialLinkFilter(GenericDateFilterSet):
    class Meta:
        model = SocialLink
        fields = ('user', 'platform')


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
