from rest_framework import viewsets

from tunga_profiles.permissions import IsAdminOrReadOnly
from tunga_support.filters import SupportPageFilter, SupportSectionFilter
from tunga_support.models import SupportSection, SupportPage
from tunga_support.serializers import SupportSectionSerializer, SupportPageSerializer


class SupportSectionViewSet(viewsets.ModelViewSet):
    """
    Support Section Resource
    """
    queryset = SupportSection.objects.all()
    serializer_class = SupportSectionSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_class = SupportSectionFilter
    lookup_field = 'slug'
    lookup_url_kwarg = 'slug'
    search_fields = ('title',)


class SupportPageViewSet(viewsets.ModelViewSet):
    """
    Support Page Resource
    """
    queryset = SupportPage.objects.all()
    serializer_class = SupportPageSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_class = SupportPageFilter
    lookup_field = 'slug'
    lookup_url_kwarg = 'slug'
    search_fields = ('title', 'content')
