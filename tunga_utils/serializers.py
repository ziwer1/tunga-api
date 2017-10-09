# -*- coding: utf-8 -*-

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django_countries.serializer_fields import CountryField
from rest_framework import serializers
from rest_framework.fields import SkipField

from tunga_profiles.models import Skill, City, UserProfile, Education, Work, Connection, BTCWallet
from tunga_profiles.utils import profile_check
from tunga_tasks.models import TaskInvoice
from tunga_utils.mixins import GetCurrentUserAnnotatedSerializerMixin
from tunga_utils.models import GenericUpload, ContactRequest, Upload, AbstractExperience, Rating


class CreateOnlyCurrentUserDefault(serializers.CurrentUserDefault):

    def set_context(self, serializer_field):
        self.is_update = serializer_field.parent.instance is not None
        super(CreateOnlyCurrentUserDefault, self).set_context(serializer_field)

    def __call__(self):
        if hasattr(self, 'is_update') and self.is_update:
            # TODO: Make sure this check is sufficient for all update scenarios
            raise SkipField()
        user = super(CreateOnlyCurrentUserDefault, self).__call__()
        if user and user.is_authenticated():
            return user
        return None


class ContentTypeAnnotatedModelSerializer(serializers.ModelSerializer):
    content_type = serializers.SerializerMethodField(read_only=True, required=False)

    def get_content_type(self, obj):
        return ContentType.objects.get_for_model(self.Meta.model).id


class DetailAnnotatedModelSerializer(serializers.ModelSerializer):
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
        fields = ('id', 'name', 'slug', 'type')


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ('id', 'name', 'slug')


class SimpleBTCWalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = BTCWallet
        exclude = ('token', 'token_secret')


class SimpleUserSerializer(serializers.ModelSerializer):
    company = serializers.CharField(read_only=True, required=False, source='userprofile.company')
    can_contribute = serializers.SerializerMethodField(required=False, read_only=True)

    class Meta:
        model = get_user_model()
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name', 'display_name', 'short_name', 'type', 'image',
            'is_developer', 'is_project_owner', 'is_project_manager', 'is_staff', 'verified', 'company', 'avatar_url',
            'can_contribute', 'date_joined'
        )

    def get_can_contribute(self, obj):
        return profile_check(obj)


class SkillsDetailsSerializer(serializers.Serializer):

    def to_representation(self, instance):
        json = dict()
        for category in instance:
            json[category] = SkillSerializer(instance=instance[category], many=True).data
        return json


class SimpleProfileSerializer(serializers.ModelSerializer):
    city = serializers.CharField()
    skills = SkillSerializer(many=True)
    country = CountryField()
    country_name = serializers.CharField()
    btc_wallet = SimpleBTCWalletSerializer()
    skills_details = SkillsDetailsSerializer()

    class Meta:
        model = UserProfile
        exclude = ('user',)


class SimpleSkillsProfileSerializer(serializers.ModelSerializer):
    city = serializers.CharField()
    skills = SkillSerializer(many=True)
    country = CountryField()
    country_name = serializers.CharField()
    skills_details = SkillsDetailsSerializer()

    class Meta:
        model = UserProfile
        fields = ('id', 'skills', 'country', 'country_name', 'city', 'bio', 'skills_details')


class SimpleUserSkillsProfileSerializer(SimpleUserSerializer):
    profile = SimpleSkillsProfileSerializer(read_only=True, required=False)

    class Meta(SimpleUserSerializer.Meta):
        model = get_user_model()
        fields = (
            'id', 'username', 'first_name', 'last_name',
            'display_name', 'short_name', 'type',
            'image', 'avatar_url', 'profile'
        )


class InvoiceUserSerializer(serializers.ModelSerializer):
    profile = SimpleProfileSerializer(read_only=True, required=False, source='userprofile')

    class Meta:
        model = get_user_model()
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name', 'display_name', 'type',
            'is_developer', 'is_project_owner', 'is_staff', 'verified', 'profile'
        )


class SimpleAbstractExperienceSerializer(serializers.ModelSerializer):
    start_month_display = serializers.CharField(read_only=True, required=False, source='get_start_month_display')
    end_month_display = serializers.CharField(read_only=True, required=False, source='get_end_month_display')

    class Meta:
        model = AbstractExperience
        exclude = ('user', 'created_at')


class AbstractExperienceSerializer(SimpleAbstractExperienceSerializer):
    user = SimpleUserSerializer(required=False, read_only=True, default=CreateOnlyCurrentUserDefault())

    class Meta:
        model = AbstractExperience
        exclude = ('created_at',)


class SimpleWorkSerializer(SimpleAbstractExperienceSerializer):

    class Meta(SimpleAbstractExperienceSerializer.Meta):
        model = Work


class SimpleEducationSerializer(SimpleAbstractExperienceSerializer):

    class Meta(SimpleAbstractExperienceSerializer.Meta):
        model = Education


class SimpleConnectionSerializer(serializers.ModelSerializer):

    class Meta:
        model = Connection
        fields = '__all__'


class SimpleUploadSerializer(serializers.ModelSerializer):
    url = serializers.CharField(required=False, read_only=True, source='file.url')
    name = serializers.SerializerMethodField(required=False, read_only=True)
    size = serializers.IntegerField(required=False, read_only=True, source='file.size')
    display_size = serializers.SerializerMethodField(required=False, read_only=True)

    class Meta:
        model = GenericUpload
        fields = ('id', 'url', 'name', 'created_at', 'size', 'display_size')

    def get_name(self, obj):
        return obj.file.name.split('/')[-1]

    def get_display_size(self, obj):
        filesize = obj.file.size
        converter = {'KB': 10**3, 'MB': 10**6, 'GB': 10**9, 'TB': 10**12}
        units = ['TB', 'GB', 'MB', 'KB']

        for label in units:
            conversion = converter[label]
            if conversion and filesize > conversion:
                return '%s %s' % (round(filesize/conversion, 2), label)
        return '%s %s' % (filesize, 'bytes')


class UploadSerializer(SimpleUploadSerializer):
    user = SimpleUserSerializer()

    class Meta(SimpleUploadSerializer.Meta):
        model = Upload
        fields = SimpleUploadSerializer.Meta.fields + ('user',)


class ContactRequestSerializer(serializers.ModelSerializer):

    class Meta:
        model = ContactRequest
        fields = ('email', 'item')


class SimpleRatingSerializer(ContentTypeAnnotatedModelSerializer):
    created_by = SimpleUserSerializer(
        required=False, read_only=True, default=CreateOnlyCurrentUserDefault()
    )
    display_criteria = serializers.CharField(required=False, read_only=True, source='get_criteria_display')

    class Meta:
        model = Rating
        exclude = ('content_type', 'object_id', 'created_at')


class TaskInvoiceSerializer(serializers.ModelSerializer, GetCurrentUserAnnotatedSerializerMixin):
    client = InvoiceUserSerializer(required=False, read_only=True)
    developer = InvoiceUserSerializer(required=False, read_only=True)
    amount = serializers.JSONField(required=False, read_only=True)
    developer_amount = serializers.SerializerMethodField(required=False, read_only=True)

    class Meta:
        model = TaskInvoice
        fields = '__all__'

    def get_developer_amount(self, obj):
        current_user = self.get_current_user()
        if current_user and current_user.is_developer:
            try:
                participation = obj.task.participation_set.get(user=current_user)
                share = obj.task.get_user_participation_share(participation.id)
                return obj.get_amount_details(share=share)
            except:
                pass
        return obj.get_amount_details(share=0)
