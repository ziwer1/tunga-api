from rest_framework import viewsets, generics
from rest_framework.permissions import IsAuthenticated, AllowAny
from tunga_profiles.models import Skill
from tunga_utils.models import ContactRequest
from tunga_utils.serializers import SkillSerializer, ContactRequestSerializer


class SkillViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Skills Resource
    """
    queryset = Skill.objects.all()
    serializer_class = SkillSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ('name', )


class ContactRequestView(generics.CreateAPIView):
    """
    Contact Request Resource
    """
    queryset = ContactRequest.objects.all()
    serializer_class = ContactRequestSerializer
    permission_classes = [AllowAny]




