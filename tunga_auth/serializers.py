from allauth.account.forms import ResetPasswordForm
from django.contrib.auth import get_user_model
from django.db.models.aggregates import Avg
from django.db.models.query_utils import Q
from rest_auth.registration.serializers import RegisterSerializer
from rest_auth.serializers import TokenSerializer, PasswordResetSerializer
from rest_framework import serializers

from tunga_auth.models import USER_TYPE_CHOICES, USER_TYPE_DEVELOPER
from tunga_utils.serializers import SimpleProfileSerializer, SimpleUserSerializer, SimpleWorkSerializer, \
    SimpleEducationSerializer


class UserSerializer(SimpleUserSerializer):
    display_name = serializers.CharField(read_only=True, required=False)
    display_type = serializers.CharField(read_only=True, required=False)
    is_developer = serializers.BooleanField(read_only=True, required=False)
    is_project_owner = serializers.BooleanField(read_only=True, required=False)
    profile = SimpleProfileSerializer(read_only=True, required=False, source='userprofile')
    work = SimpleWorkSerializer(many=True, source='work_set', read_only=True, required=False)
    education = SimpleEducationSerializer(many=True, source='education_set', read_only=True, required=False)
    can_connect = serializers.SerializerMethodField(read_only=True, required=False)
    request = serializers.SerializerMethodField(read_only=True, required=False)
    tasks_created = serializers.SerializerMethodField(read_only=True, required=False)
    tasks_completed = serializers.SerializerMethodField(read_only=True, required=False)
    satisfaction = serializers.SerializerMethodField(read_only=True, required=False)

    class Meta:
        model = get_user_model()
        exclude = ('password', 'is_superuser', 'groups', 'user_permissions', 'is_active')
        read_only_fields = (
            'username', 'email', 'date_joined', 'last_login', 'is_staff'
        )

    def get_can_connect(self, obj):
        request = self.context.get("request", None)
        if request:
            user = getattr(request, "user", None)
            if user:
                if not user.is_developer and not obj.is_developer:
                    return False
                has_requested = obj.connections_initiated.filter(to_user=user).count()
                if has_requested:
                    return False
                has_accepted_or_been_requested = obj.connection_requests.filter(
                    Q(accepted=True) | Q(responded=False), from_user=user).count() > 0
                return not has_accepted_or_been_requested
        return False

    def get_request(self, obj):
        request = self.context.get("request", None)
        if request:
            user = getattr(request, "user", None)
            if user:
                try:
                    connection = obj.connections_initiated.get(to_user=user, responded=False)
                    return connection.id
                except:
                    pass
        return None

    def get_tasks_created(self, obj):
        return obj.tasks_created.count()

    def get_tasks_completed(self, obj):
        return obj.participation_set.filter(task__closed=True, accepted=True).count()

    def get_satisfaction(self, obj):
        score = None
        if obj.type == USER_TYPE_DEVELOPER:
            score = obj.participation_set.filter(
                task__closed=True, accepted=True
            ).aggregate(satisfaction=Avg('task__satisfaction'))['satisfaction']
            if score:
                score = '{:0,.0f}%'.format(score*10)
        return score



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


class TungaRegisterSerializer(RegisterSerializer):
    type = serializers.ChoiceField(required=True, choices=USER_TYPE_CHOICES, allow_blank=False, allow_null=False)
    first_name = serializers.CharField(required=True, allow_blank=False, allow_null=False)
    last_name = serializers.CharField(required=True, allow_blank=False, allow_null=False)

    def save(self, request):
        user = super(TungaRegisterSerializer, self).save(request)
        user.type = self.initial_data['type']
        user.first_name = self.initial_data['first_name']
        user.last_name = self.initial_data['last_name']
        user.save()
        return user


class TungaTokenSerializer(TokenSerializer):
    user = serializers.SerializerMethodField(read_only=True, required=False)

    class Meta:
        model = TokenSerializer.Meta.model
        fields = ('key', 'user')

    def get_user(self, obj):
        return SimpleUserSerializer(obj.user).data


class TungaPasswordResetSerializer(PasswordResetSerializer):

    password_reset_form_class = ResetPasswordForm

