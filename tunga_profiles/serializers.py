from rest_framework import serializers

from tunga_auth.serializers import SimpleUserSerializer
from tunga_utils.serializers import SimpleProfileSerializer, CreateOnlyCurrentUserDefault, DetailAnnotatedSerializer, \
    ContentTypeAnnotatedSerializer
from tunga_profiles.models import UserProfile, Education, Work, Connection, SocialPlatform, SocialLink


class ProfileDetailsSerializer(SimpleProfileSerializer):
    user = SimpleUserSerializer()

    class Meta:
        model = UserProfile
        fields = ('user', 'city', 'skills')


class ProfileSerializer(DetailAnnotatedSerializer):
    user = serializers.PrimaryKeyRelatedField(required=False, read_only=True, default=CreateOnlyCurrentUserDefault)
    city = serializers.CharField()
    skills = serializers.CharField()

    class Meta:
        model = UserProfile
        details_serializer = ProfileDetailsSerializer


class SocialPlatformSerializer(serializers.ModelSerializer):
    created_by = serializers.HiddenField(required=False, default=CreateOnlyCurrentUserDefault)

    class Meta:
        model = SocialPlatform
        exclude = ('created_at',)


class SocialLinkDetailsSerializer(DetailAnnotatedSerializer):
    user = SimpleUserSerializer()
    platform = SocialPlatformSerializer()

    class Meta:
        model = SocialLink
        fields = ('user', 'platform')


class SocialLinkSerializer(DetailAnnotatedSerializer):
    user = serializers.PrimaryKeyRelatedField(required=False, read_only=True, default=CreateOnlyCurrentUserDefault)

    class Meta:
        model = SocialLink
        exclude = ('created_at',)
        details_serializer = SocialLinkDetailsSerializer


class EducationSerializer(serializers.ModelSerializer):
    user = SimpleUserSerializer(required=False, read_only=True, default=CreateOnlyCurrentUserDefault)
    institution = serializers.CharField()

    class Meta:
        model = Education
        exclude = ('created_at',)


class WorkSerializer(serializers.ModelSerializer):
    user = SimpleUserSerializer(required=False, read_only=True, default=CreateOnlyCurrentUserDefault)

    class Meta:
        model = Work
        exclude = ('created_at',)


class ConnectionDetailsSerializer(serializers.ModelSerializer):
    from_user = SimpleUserSerializer()
    to_user = SimpleUserSerializer()

    class Meta:
        model = Connection
        fields = ('from_user', 'to_user')


class ConnectionSerializer(DetailAnnotatedSerializer):
    from_user = serializers.PrimaryKeyRelatedField(required=False, read_only=True, default=CreateOnlyCurrentUserDefault)

    class Meta:
        model = Connection
        exclude = ('created_at',)
        details_serializer = ConnectionDetailsSerializer

