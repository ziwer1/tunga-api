from tunga_settings.models import UserSwitchSetting, SwitchSetting


def check_switch_setting(user, slug):
    try:
        setting = SwitchSetting.objects.get(slug=slug)
    except SwitchSetting.DoesNotExist:
        return False
    try:
        switch = UserSwitchSetting.objects.get(user=user, setting=setting)
        return switch.value
    except UserSwitchSetting.DoesNotExist:
        return setting.default_value
