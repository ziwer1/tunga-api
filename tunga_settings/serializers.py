from rest_framework import serializers

from tunga_settings.models import Setting, SwitchSetting, VisibilitySetting, UserSetting, UserSwitchSetting, \
    UserVisibilitySetting


class SimpleSettingSerializer(serializers.ModelSerializer):

    class Meta:
        model = Setting
        exclude = ('created_by', 'created_at')


class SimpleSwitchSettingSerializer(SimpleSettingSerializer):

    class Meta(SimpleSettingSerializer.Meta):
        model = SwitchSetting


class SimpleVisibilitySettingSerializer(SimpleSettingSerializer):

    class Meta(SimpleSettingSerializer.Meta):
        model = VisibilitySetting


class UserSettingSerializer(serializers.ModelSerializer):

    class Meta:
        model = UserSetting
        exclude = ('created_at', 'updated_at')


class UserSwitchSettingSerializer(UserSettingSerializer):

    class Meta(UserSettingSerializer.Meta):
        model = UserSwitchSetting


class UserVisibilitySettingSerializer(UserSettingSerializer):

    class Meta(UserSettingSerializer.Meta):
        model = UserVisibilitySetting
