from django.contrib.contenttypes.models import ContentType
from django_countries.serializer_fields import CountryField
from rest_framework import serializers
from rest_framework.fields import SkipField

from tunga_profiles.models import Skill, City, Institution, UserProfile
from tunga_utils.models import GenericUpload, ContactRequest, Upload


class CreateOnlyCurrentUserDefault(serializers.CurrentUserDefault):

    def set_context(self, serializer_field):
        self.is_update = serializer_field.parent.instance is not None
        super(CreateOnlyCurrentUserDefault, self).set_context(serializer_field)

    def __call__(self):
        if hasattr(self, 'is_update') and self.is_update:
            # TODO: Make sure this check is sufficient for all update scenarios
            raise SkipField()
        super(CreateOnlyCurrentUserDefault, self).__call__()


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
    city = serializers.CharField()
    skills = SkillSerializer(many=True)
    country = CountryField()
    country_name = serializers.CharField()

    class Meta:
        model = UserProfile
        exclude = ('user',)


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

    class Meta(SimpleUploadSerializer.Meta):
        model = Upload


class ContactRequestSerializer(serializers.ModelSerializer):

    class Meta:
        model = ContactRequest
        fields = ('email',)
