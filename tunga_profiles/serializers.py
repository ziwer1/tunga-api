from django.core.validators import validate_email
from django_countries.serializer_fields import CountryField
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from tunga_profiles.models import UserProfile, Education, Work, Connection, DeveloperApplication, DeveloperInvitation
from tunga_profiles.notifications import send_developer_invited_email
from tunga_utils.constants import PAYMENT_METHOD_MOBILE_MONEY, PAYMENT_METHOD_BTC_ADDRESS
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
    first_name = serializers.CharField(required=False, write_only=True, max_length=20)
    last_name = serializers.CharField(required=False, write_only=True, max_length=20)
    city = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    skills = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    country = CountryField(required=False)

    class Meta:
        model = UserProfile
        exclude = ()
        details_serializer = ProfileDetailsSerializer

    def validate(self, attrs):
        payment_method = attrs.get('payment_method', None)
        if payment_method == PAYMENT_METHOD_MOBILE_MONEY:
            mobile_money_cc = attrs.get('mobile_money_cc', None)
            mobile_money_number = attrs.get('mobile_money_number', None)
            if not mobile_money_cc:
                raise ValidationError({'mobile_money_cc': 'Enter the country code for your mobile number'})
            if not mobile_money_number:
                raise ValidationError({'mobile_money_number': 'Enter your mobile money number'})
        elif payment_method == PAYMENT_METHOD_BTC_ADDRESS:
            if not attrs.get('btc_address', None):
                raise ValidationError({'btc_address': 'Enter a bitcoin address'})
        return attrs

    def save_profile(self, validated_data, instance=None):
        user_data = self.get_user_data(validated_data)
        skills = None
        city = None
        languages = None
        frameworks = None
        platforms = None
        libraries = None
        storage = None
        third_party_apis = None

        if 'skills' in validated_data:
            skills = validated_data.pop('skills')
        if 'city' in validated_data:
            city = validated_data.pop('city')
        if 'languages' in validated_data:
            languages = validated_data.pop('languages')
        if 'frameworks' in validated_data:
            frameworks = validated_data.pop('frameworks')
        if 'platforms' in validated_data:
            platforms = validated_data.pop('platforms')
        if 'libraries' in validated_data:
            libraries = validated_data.pop('libraries')
        if 'storage' in validated_data:
            storage = validated_data.pop('storage')
        if 'third_party_apis' in validated_data:
            third_party_apis = validated_data.pop('third_party_apis')
        

        if instance:
            instance = super(ProfileSerializer, self).update(instance, validated_data)
        else:
            instance = super(ProfileSerializer, self).create(validated_data)
        self.save_user_info(instance, user_data)
        self.save_skills(instance, skills)
        self.save_city(instance, city)
        self.save_languages(instance, languages)
        self.save_frameworks(instance, frameworks)
        self.save_platforms(instance, platforms)
        self.save_libraries(instance, libraries)
        self.save_storage(instance, storage)
        self.save_third_party_apis(instance, third_party_apis)
        return instance

    def create(self, validated_data):
        return self.save_profile(validated_data)

    def update(self, instance, validated_data):
        return self.save_profile(validated_data, instance)

    def get_user_data(self, validated_data):
        user_data = dict()
        for user_key in ['first_name', 'last_name']:
            if user_key in validated_data:
                user_data[user_key] = validated_data.pop(user_key)
        return user_data

    def save_user_info(self, instance, user_data):
        user = instance.user
        if user:
            first_name = user_data.get('first_name')
            last_name = user_data.get('last_name')
            if first_name or last_name:
                user.first_name = first_name or user.first_name
                user.last_name = last_name or user.last_name
                user.save()

    def save_skills(self, profile, skills):
        if skills is not None:
            profile.skills = skills
            profile.save()

    def save_city(self, profile, city):
        if city:
            profile.city = city
            profile.save()

    def save_languages(self, profile, languages):
        if languages is not None:
            profile.languages = languages
            profile.save()

    def save_frameworks(self, profile, frameworks):
        if frameworks is not None:
            profile.frameworks = frameworks
            profile.save()

    def save_platforms(self, profile, platforms):
        if platforms is not None:
            profile.platforms = platforms
            profile.save()

    def save_libraries(self, profile, libraries):
        if libraries is not None:
            profile.libraries = libraries
            profile.save()

    def save_storage(self, profile, storage):
        if storage is not None:
            profile.storage = storage
            profile.save()

    def save_third_party_apis(self, profile, third_party_apis):
        if third_party_apis is not None:
            profile.third_party_apis = third_party_apis
            profile.save()


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


class DeveloperInvitationSerializer(serializers.ModelSerializer):
    created_by = serializers.PrimaryKeyRelatedField(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())
    display_name = serializers.CharField(required=False, read_only=True)
    # resend = serializers.BooleanField(required=False, write_only=True, default=False)

    class Meta:
        model = DeveloperInvitation
        exclude = ('invitation_key', 'used', 'used_at')

    def is_valid(self, raise_exception=False):
        resend = self.initial_data.get('resend', False)
        email = self.initial_data.get('email', False)
        is_valid = super(DeveloperInvitationSerializer, self).is_valid(raise_exception=raise_exception and not resend)
        if resend and email:
            try:
                invite = DeveloperInvitation.objects.get(email=email)
                self.instance = invite
                if invite:
                    self._errors = {}

                    invite.first_name = self.initial_data.get('first_name', invite.first_name)
                    invite.last_name = self.initial_data.get('last_name', invite.last_name)
                    invite.type = self.initial_data.get('type', invite.type)
                    invite.save()

                    send_developer_invited_email.delay(invite.id, resend=True)
                    return True
            except:
                pass
        if self._errors and raise_exception:
            raise ValidationError(self.errors)
        return is_valid

    def create(self, validated_data):
        resend = self.initial_data.get('resend', False)
        if resend and self.instance:
            return self.instance
        return super(DeveloperInvitationSerializer, self).create(validated_data)

