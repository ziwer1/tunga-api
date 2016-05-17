from rest_framework import viewsets, views, status, generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from tunga_settings.filterbackends import UserSettingFilterBackend
from tunga_settings.models import UserSwitchSetting, UserVisibilitySetting

from tunga_settings.serializers import UserSwitchSettingSerializer, UserVisibilitySettingSerializer, \
    CompoundUserSettingsSerializer, ReadUserSettingsSerializer
from tunga_utils.filterbackends import DEFAULT_FILTER_BACKENDS


class UserSwitchSettingViewSet(viewsets.ModelViewSet):
    """
    Switch Settings Resource
    """
    queryset = UserSwitchSetting.objects.all()
    serializer_class = UserSwitchSettingSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = DEFAULT_FILTER_BACKENDS + (UserSettingFilterBackend,)


class UserVisibilitySettingViewSet(viewsets.ModelViewSet):
    """
    Visibility Settings Resource
    """
    queryset = UserVisibilitySetting.objects.all()
    serializer_class = UserVisibilitySettingSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = DEFAULT_FILTER_BACKENDS + (UserSettingFilterBackend,)


class UserSettingsView(generics.GenericAPIView):
    """
    User Settings Resource
    Manage settings of current user
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ReadUserSettingsSerializer

    def get_object(self):
        user = self.request.user
        if user is not None and user.is_authenticated():
            return user
        else:
            return None

    def _unauthorized_response(self):
        return Response(
            {'status': 'Unauthorized', 'message': 'You are not logged in'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    def get(self, request):
        user = self.get_object()
        if user is None:
            return self._unauthorized_response()
        switches = UserSwitchSetting.objects.filter(user=user)
        visibility = UserVisibilitySetting.objects.filter(user=user)
        settings = {'switches': switches, 'visibility': visibility}
        serializer = ReadUserSettingsSerializer(settings)
        return Response(serializer.data)

    def put(self, request):
        user = self.get_object()
        if user is None:
            return self._unauthorized_response()

        switches = request.data.get('switches', None)
        visibility = request.data.get('visibility', None)
        settings = {
            'switches': [{'setting': k, 'value': v} for k, v in switches.iteritems()] if isinstance(switches, dict) else [],
            'visibility': [{'setting': k, 'value': v} for k, v in visibility.iteritems()] if isinstance(visibility, dict) else []
        }

        serializer = CompoundUserSettingsSerializer(data=settings, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user_settings = serializer.save()
        print user_settings
        read_serializer = ReadUserSettingsSerializer(user_settings)
        return Response(read_serializer.data)
