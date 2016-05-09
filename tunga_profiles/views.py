from django.db.models.aggregates import Max
from django.db.models.expressions import F, Case, When
from django.db.models.fields import DateTimeField
from django.db.models.query_utils import Q
from django_countries.fields import CountryField
from rest_framework import viewsets, generics, views, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from tunga_auth.models import USER_TYPE_PROJECT_OWNER
from tunga_messages.models import Message
from tunga_profiles.filters import EducationFilter, WorkFilter, ConnectionFilter, SocialLinkFilter
from tunga_profiles.models import UserProfile, Education, Work, Connection, SocialLink
from tunga_profiles.serializers import ProfileSerializer, EducationSerializer, WorkSerializer, ConnectionSerializer, \
    SocialLinkSerializer


class ProfileView(generics.CreateAPIView, generics.RetrieveUpdateDestroyAPIView):
    """
    Manage current user's profile info
    """
    queryset = UserProfile.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        user = self.request.user
        if user is not None and user.is_authenticated():
            try:
                return user.userprofile
            except:
                pass
        return None


class SocialLinkViewSet(viewsets.ModelViewSet):
    """
    Manage Education Profile
    """
    queryset = SocialLink.objects.all()
    serializer_class = SocialLinkSerializer
    permission_classes = [IsAuthenticated]
    filter_class = SocialLinkFilter
    search_fields = ('institution__name', 'award')


class EducationViewSet(viewsets.ModelViewSet):
    """
    Manage Education Profile
    """
    queryset = Education.objects.all()
    serializer_class = EducationSerializer
    permission_classes = [IsAuthenticated]
    filter_class = EducationFilter
    search_fields = ('institution__name', 'award')


class WorkViewSet(viewsets.ModelViewSet):
    """
    Manage Work Profile
    """
    queryset = Work.objects.all()
    serializer_class = WorkSerializer
    permission_classes = [IsAuthenticated]
    filter_class = WorkFilter
    search_fields = ('company', 'position')


class ConnectionViewSet(viewsets.ModelViewSet):
    """
    Manage Connections
    """
    queryset = Connection.objects.all()
    serializer_class = ConnectionSerializer
    permission_classes = [IsAuthenticated]
    filter_class = ConnectionFilter
    search_fields = ('from_user__username', 'to_user__username')


class CountryListView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        countries = []
        for country in CountryField().get_choices():
            countries.append({'code': country[0], 'name': country[1]})
        return Response(
            countries,
            status=status.HTTP_200_OK
        )


class NotificationView(views.APIView):
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
        aggregator = Max(
            Case(
                When(
                    Q(reception__user=request.user) &
                    Q(reception__message__id=F('id')),
                    then='reception__read_at'
                ),
                output_field=DateTimeField())
        )
        messages = Message.objects.annotate(my_read_at=aggregator).filter(
            (
                Q(recipients=user) |
                (
                    Q(is_broadcast=True) & (
                        (
                            Q(user__connections_initiated__accepted=True) &
                            Q(user__connections_initiated__to_user=request.user)
                        ) |
                        (
                            Q(user__connection_requests__from_user=request.user) &
                            Q(user__connection_requests__accepted=True)
                        )
                    )
                )
            ) & (Q(created_at__gt=F('my_read_at')) | Q(my_read_at=None))
        ).count()
        requests = user.connection_requests.filter(responded=False).count()
        tasks = user.tasks_created.filter(closed=False).count() + user.participation_set.filter((Q(accepted=True) | Q(responded=False)), user=user).count()
        profile = None
        profile_notifications = {'count': 0, 'missing': [], 'improve': [], 'more': [], 'section': None}
        try:
            profile = user.userprofile
        except:
            profile_notifications['missing'] = ['skills', 'bio', 'country', 'city', 'street', 'plot_number', 'phone_number']

        if not user.image:
            profile_notifications['missing'].append('image')

        if profile:
            skills = profile.skills.count()
            if skills == 0:
                profile_notifications['missing'].append('skills')
            elif skills < 3:
                profile_notifications['more'].append('skills')

            if not profile.bio:
                profile_notifications['missing'].append('bio')

            if not profile.country:
                profile_notifications['missing'].append('country')
            if not profile.city:
                profile_notifications['missing'].append('city')
            if not profile.street:
                profile_notifications['missing'].append('street')
            if not profile.plot_number:
                profile_notifications['missing'].append('plot_number')
            if not profile.phone_number:
                profile_notifications['missing'].append('phone_number')

            if user.type == USER_TYPE_PROJECT_OWNER and not profile.company:
                profile_notifications['missing'].append('company')

        profile_notifications['count'] = len(profile_notifications['missing']) + len(profile_notifications['more']) \
                                         + len(profile_notifications['improve'])

        return Response(
            {'messages': messages, 'requests': requests, 'tasks': tasks, 'profile': profile_notifications},
            status=status.HTTP_200_OK
        )
