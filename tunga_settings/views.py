from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from tunga_settings.filterbackends import UserSettingFilterBackend
from tunga_settings.models import UserSwitchSetting, UserVisibilitySetting

from tunga_settings.serializers import UserSwitchSettingSerializer, UserVisibilitySettingSerializer
from tunga_utils.filterbackends import DEFAULT_FILTER_BACKENDS


class UserSwitchSettingViewSet(viewsets.ModelViewSet):
    """
    Manage Switch Settings
    """
    queryset = UserSwitchSetting.objects.all()
    serializer_class = UserSwitchSettingSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = DEFAULT_FILTER_BACKENDS + (UserSettingFilterBackend,)


class UserVisibilitySettingViewSet(viewsets.ModelViewSet):
    """
    Manage Visibility Settings
    """
    queryset = UserVisibilitySetting.objects.all()
    serializer_class = UserVisibilitySettingSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = DEFAULT_FILTER_BACKENDS + (UserSettingFilterBackend,)
