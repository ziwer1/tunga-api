from django.contrib.auth import get_user_model
from rest_framework import serializers

from tunga_utils.serializers import SimpleProfileSerializer


class SimpleUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ('id', 'username', 'first_name', 'last_name', 'type', 'image')


class UserSerializer(SimpleUserSerializer):
    profile = SimpleProfileSerializer(read_only=True, required=False, source='userprofile')

    class Meta:
        model = get_user_model()
        exclude = ('password', 'is_superuser', 'groups', 'user_permissions', 'is_active')
        read_only_fields = (
            'username', 'email', 'date_joined', 'last_login', 'is_staff'
        )


class AccountInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ('username', 'email', 'first_name', 'last_name', 'type', 'image')

    def validate(self, attrs):
        super(AccountInfoSerializer, self).validate(attrs)

        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if not user:
            raise serializers.ValidationError('Something went wrong')

        password = self.initial_data.get('password', None)
        if not password or not user.check_password(password):
            raise serializers.ValidationError({'password': 'Wrong password'})
        return attrs
