from rest_framework import serializers

from tunga_pages.models import SkillPage, SkillPageProfile
from tunga_utils.serializers import SimpleUserSkillsProfileSerializer, SkillSerializer


class SkillPageProfileSerializer(serializers.ModelSerializer):
    profiles = serializers.JSONField(read_only=True, required=False, source='skillpageprofile_set')
    user = SimpleUserSkillsProfileSerializer(read_only=True, required=False)

    class Meta:
        model = SkillPageProfile
        exclude = ('created_by',)


class SkillPageSerializer(serializers.ModelSerializer):
    profiles = SkillPageProfileSerializer(read_only=True, required=False, source='skillpageprofile_set', many=True)
    skill = SkillSerializer(read_only=True, required=False)

    class Meta:
        model = SkillPage
        exclude = ('created_by',)
