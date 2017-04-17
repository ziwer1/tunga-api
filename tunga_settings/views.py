from django.utils import six
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from tunga_settings.models import UserSwitchSetting, UserVisibilitySetting, SwitchSetting
from tunga_settings.serializers import UserSettingsUpdateSerializer, UserSettingsSerializer


class UserSettingsView(generics.GenericAPIView):
    """
    User Settings Resource
    Manage settings of current user
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserSettingsUpdateSerializer
    queryset = SwitchSetting.objects.all()

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
        serializer = UserSettingsSerializer(settings)
        return Response(serializer.data)

    def put(self, request):
        user = self.get_object()
        if user is None:
            return self._unauthorized_response()

        switches = request.data.get('switches', None)
        visibility = request.data.get('visibility', None)
        settings = {
            'switches': [{'setting': k, 'value': v} for k, v in six.iteritems(switches)] if isinstance(switches, dict) else [],
            'visibility': [{'setting': k, 'value': v} for k, v in six.iteritems(visibility)] if isinstance(visibility, dict) else []
        }

        serializer = UserSettingsUpdateSerializer(data=settings, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user_settings = serializer.save()
        read_serializer = UserSettingsSerializer(user_settings)
        return Response(read_serializer.data)
