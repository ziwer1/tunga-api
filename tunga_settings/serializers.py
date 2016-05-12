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


class AuthUserSettingSerializer(serializers.ModelSerializer):

    class Meta:
        model = UserSetting
        exclude = ('id', 'user', 'created_at', 'updated_at')


class AuthUserSwitchSettingSerializer(AuthUserSettingSerializer):

    class Meta(AuthUserSettingSerializer.Meta):
        model = UserSwitchSetting


class AuthUserVisibilitySettingSerializer(AuthUserSettingSerializer):

    class Meta(AuthUserSettingSerializer.Meta):
        model = UserVisibilitySetting


class CompoundUserSettingsSerializer(serializers.Serializer):
    switches = AuthUserSwitchSettingSerializer(many=True, required=False, write_only=True)
    visibility = AuthUserVisibilitySettingSerializer(many=True, required=False, write_only=True)

    def create(self, validated_data):
        settings = {'switches': [], 'visibility': []}
        request = self.context.get("request", None)
        if request:
            user = getattr(request, "user", None)
            if user:
                switches = validated_data.get('switches', [])
                for setting in switches:
                    settings['switches'].append(
                        UserSwitchSetting.objects.update_or_create(
                            user=user, setting=setting['setting'], defaults=setting
                        )[0]
                    )
                visibility = validated_data.get('visibility', [])
                for setting in visibility:
                    settings['visibility'].append(
                        UserVisibilitySetting.objects.update_or_create(
                            user=user, setting=setting['setting'], defaults=setting
                        )[0]
                    )
        return settings

    def update(self, instance, validated_data):
        return self.create(validated_data)


class ReadUserSettingsSerializer(serializers.Serializer):
    visibility = serializers.SerializerMethodField(required=False, read_only=True)
    switches = serializers.SerializerMethodField(required=False, read_only=True)

    def get_switches(self, obj):
        settings = {}

        for item in SwitchSetting.objects.all():
            settings.update({item.slug: item.default_value})

        switches = obj.get('switches', [])

        for item in switches:
            settings.update({item.setting.slug: item.value})
        return settings

    def get_visibility(self, obj):
        settings = {}

        for item in VisibilitySetting.objects.all():
            settings.update({item.slug: item.default_value})

        visibility = obj.get('visibility', [])

        for item in visibility:
            print type(item)
            print item
            settings.update({item.setting.slug: item.value})
        return settings
