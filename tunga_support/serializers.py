from rest_framework import serializers

from tunga_support.models import SupportPage, SupportSection


class SimpleSupportSectionSerializer(serializers.ModelSerializer):

    class Meta:
        model = SupportSection
        exclude = ('created_at', 'created_by')


class SimpleSupportPageSerializer(serializers.ModelSerializer):

    class Meta:
        model = SupportPage
        exclude = ('created_at', 'created_by')


class SupportSectionSerializer(SimpleSupportSectionSerializer):
    pages = SimpleSupportPageSerializer(many=True)

    class Meta(SimpleSupportSectionSerializer.Meta):
        pass


class SupportPageSerializer(SimpleSupportPageSerializer):
    section = SimpleSupportSectionSerializer()

    class Meta(SimpleSupportPageSerializer.Meta):
        pass
