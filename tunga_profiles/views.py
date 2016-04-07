from rest_framework import viewsets, generics
from rest_framework.permissions import IsAuthenticated

from tunga_profiles.filters import EducationFilter, WorkFilter, ConnectionFilter, SocialLinkFilter
from tunga_profiles.models import UserProfile, Education, Work, Connection, SocialLink
from tunga_profiles.serializers import ProfileSerializer, EducationSerializer, WorkSerializer, ConnectionSerializer, \
    SocialLinkSerializer


class ProfileView(generics.CreateAPIView, generics.RetrieveUpdateDestroyAPIView):
    """
    Manage current user's profile info
    """
    queryset = UserProfile.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        user = self.request.user
        if user is not None and user.is_authenticated():
            try:
                return user.userprofile
            except:
                pass
        return None


class SocialLinkViewSet(viewsets.ModelViewSet):
    """
    Manage Education Profile
    """
    queryset = SocialLink.objects.all()
    serializer_class = SocialLinkSerializer
    permission_classes = [IsAuthenticated]
    filter_class = SocialLinkFilter
    search_fields = ('institution__name', 'award')


class EducationViewSet(viewsets.ModelViewSet):
    """
    Manage Education Profile
    """
    queryset = Education.objects.all()
    serializer_class = EducationSerializer
    permission_classes = [IsAuthenticated]
    filter_class = EducationFilter
    search_fields = ('institution__name', 'award')


class WorkViewSet(viewsets.ModelViewSet):
    """
    Manage Work Profile
    """
    queryset = Work.objects.all()
    serializer_class = WorkSerializer
    permission_classes = [IsAuthenticated]
    filter_class = WorkFilter
    search_fields = ('company', 'position')


class ConnectionViewSet(viewsets.ModelViewSet):
    """
    Manage Connections
    """
    queryset = Connection.objects.all()
    serializer_class = ConnectionSerializer
    permission_classes = [IsAuthenticated]
    filter_class = ConnectionFilter
    search_fields = ('from_user__username', 'to_user__username')
