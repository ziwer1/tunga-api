from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from tunga_profiles.models import Skill, City, Institution, UserProfile

CreateOnlyCurrentUserDefault = serializers.CreateOnlyDefault(serializers.CurrentUserDefault())


class ContentTypeAnnotatedSerializer(serializers.ModelSerializer):
    content_type = serializers.SerializerMethodField(read_only=True, required=False)

    def get_content_type(self, obj):
        return ContentType.objects.get_for_model(self.Meta.model).id


class DetailAnnotatedSerializer(serializers.ModelSerializer):
    details = serializers.SerializerMethodField(read_only=True, required=False)

    class Meta:
        details_serializer = None

    def get_details(self, obj):
        try:
            if self.Meta.details_serializer:
                return self.Meta.details_serializer(obj).data
        except AttributeError:
            return None


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ('id', 'name', 'slug')


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ('id', 'name', 'slug')


class InstitutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Institution
        fields = ('id', 'name', 'slug')


class SimpleProfileSerializer(serializers.ModelSerializer):
    city = CitySerializer()
    skills = SkillSerializer(many=True)

    class Meta:
        model = UserProfile
        exclude = ('user',)