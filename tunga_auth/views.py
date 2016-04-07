from django.contrib.auth import get_user_model
from django.shortcuts import render
from rest_framework import views, status, generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from tunga_auth.serializers import SimpleUserSerializer, UserSerializer, AccountInfoSerializer


class VerifyUserView(views.APIView):
    """
    Verifies Current user.
    Returns user object if user is logged in, otherwise 401 Unauthorized
    """
    permission_classes = [IsAuthenticated]

    def get_object(self, request):
        user = request.user
        if user is not None and user.is_authenticated():
            return user
        else:
            return None

    def get(self, request):
        user = self.get_object(request)
        if user is None:
            return Response(
                {'status': 'Unauthorized', 'message': 'You are not logged in'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        serializer = SimpleUserSerializer(user)
        return Response(serializer.data)


class AuthUserView(generics.RetrieveUpdateAPIView):
    """
    Manage current user's basic info
    """
    queryset = get_user_model().objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        user = self.request.user
        if user is not None and user.is_authenticated():
            return user
        else:
            return None


class AccountInfoView(generics.RetrieveUpdateAPIView):
    """
    Manage current user's account info
    """
    queryset = get_user_model().objects.all()
    serializer_class = AccountInfoSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        user = self.request.user
        if user is not None and user.is_authenticated():
            return user
        else:
            return None
