from django_countries.serializer_fields import CountryField
from rest_framework import serializers

from tunga_profiles.models import UserProfile, Education, Work, Connection, SocialPlatform, SocialLink, DeveloperApplication
from tunga_utils.serializers import SimpleProfileSerializer, CreateOnlyCurrentUserDefault, SimpleUserSerializer, AbstractExperienceSerializer, \
    DetailAnnotatedModelSerializer, SimpleBTCWalletSerializer


class ProfileDetailsSerializer(SimpleProfileSerializer):
    user = SimpleUserSerializer()
    btc_wallet = SimpleBTCWalletSerializer()

    class Meta:
        model = UserProfile
        fields = ('user', 'city', 'skills', 'btc_wallet')


class ProfileSerializer(DetailAnnotatedModelSerializer):
    user = serializers.PrimaryKeyRelatedField(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())
    city = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    skills = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    country = CountryField(required=False)

    class Meta:
        model = UserProfile
        details_serializer = ProfileDetailsSerializer

    def create(self, validated_data):
        skills = None
        city = None
        if 'skills' in validated_data:
            skills = validated_data.pop('skills')
        if 'city' in validated_data:
            city = validated_data.pop('city')
        instance = super(ProfileSerializer, self).create(validated_data)
        self.save_skills(instance, skills)
        self.save_city(instance, city)
        return instance

    def update(self, instance, validated_data):
        skills = None
        city = None
        if 'skills' in validated_data:
            skills = validated_data.pop('skills')
        if 'city' in validated_data:
            city = validated_data.pop('city')
        instance = super(ProfileSerializer, self).update(instance, validated_data)
        self.save_skills(instance, skills)
        self.save_city(instance, city)
        return instance

    def save_skills(self, profile, skills):
        if skills is not None:
            profile.skills = skills
            profile.save()

    def save_city(self, profile, city):
        if city:
            profile.city = city
            profile.save()


class SocialPlatformSerializer(serializers.ModelSerializer):
    created_by = serializers.HiddenField(required=False, default=CreateOnlyCurrentUserDefault())

    class Meta:
        model = SocialPlatform
        exclude = ('created_at',)


class SocialLinkDetailsSerializer(DetailAnnotatedModelSerializer):
    user = SimpleUserSerializer()
    platform = SocialPlatformSerializer()

    class Meta:
        model = SocialLink
        fields = ('user', 'platform')


class SocialLinkSerializer(DetailAnnotatedModelSerializer):
    user = serializers.PrimaryKeyRelatedField(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())

    class Meta:
        model = SocialLink
        exclude = ('created_at',)
        details_serializer = SocialLinkDetailsSerializer


class EducationSerializer(AbstractExperienceSerializer):

    class Meta(AbstractExperienceSerializer.Meta):
        model = Education


class WorkSerializer(AbstractExperienceSerializer):

    class Meta(AbstractExperienceSerializer.Meta):
        model = Work


class ConnectionDetailsSerializer(serializers.ModelSerializer):
    from_user = SimpleUserSerializer()
    to_user = SimpleUserSerializer()

    class Meta:
        model = Connection
        fields = ('from_user', 'to_user')


class ConnectionSerializer(DetailAnnotatedModelSerializer):
    from_user = serializers.PrimaryKeyRelatedField(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())

    class Meta:
        model = Connection
        exclude = ('created_at',)
        details_serializer = ConnectionDetailsSerializer


class DeveloperApplicationSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(required=False, read_only=True)

    class Meta:
        model = DeveloperApplication
        exclude = ('confirmation_key', 'confirmation_sent_at', 'used', 'used_at')
