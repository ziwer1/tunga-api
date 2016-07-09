from django.db.models.query_utils import Q
from django.shortcuts import get_object_or_404
from django_countries.fields import CountryField
from dry_rest_permissions.generics import DRYObjectPermissions, DRYPermissions
from rest_framework import viewsets, generics, views, status
from rest_framework.decorators import list_route
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from tunga_auth.models import USER_TYPE_PROJECT_OWNER
from tunga_messages.filterbackends import new_messages_filter
from tunga_messages.models import Message
from tunga_profiles.filterbackends import ConnectionFilterBackend
from tunga_profiles.filters import EducationFilter, WorkFilter, ConnectionFilter, SocialLinkFilter, \
    DeveloperApplicationFilter
from tunga_profiles.models import UserProfile, Education, Work, Connection, SocialLink, DeveloperApplication
from tunga_profiles.permissions import IsAdminOrCreateOnly
from tunga_profiles.serializers import ProfileSerializer, EducationSerializer, WorkSerializer, ConnectionSerializer, \
    SocialLinkSerializer, DeveloperApplicationSerializer
from tunga_utils import github
from tunga_utils.filterbackends import DEFAULT_FILTER_BACKENDS
from tunga_utils.github import ISSUE_FIELDS, extract_repo_info
from tunga_utils.views import get_social_token


class ProfileView(generics.CreateAPIView, generics.RetrieveUpdateDestroyAPIView):
    """
    User Profile Info Resource
    """
    queryset = UserProfile.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated, DRYObjectPermissions]

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
    Social Link Resource
    """
    queryset = SocialLink.objects.all()
    serializer_class = SocialLinkSerializer
    permission_classes = [IsAuthenticated, DRYObjectPermissions]
    filter_class = SocialLinkFilter


class EducationViewSet(viewsets.ModelViewSet):
    """
    Education Info Resource
    """
    queryset = Education.objects.all()
    serializer_class = EducationSerializer
    permission_classes = [IsAuthenticated, DRYPermissions]
    filter_class = EducationFilter
    search_fields = ('institution__name', 'award')


class WorkViewSet(viewsets.ModelViewSet):
    """
    Work Info Resource
    """
    queryset = Work.objects.all()
    serializer_class = WorkSerializer
    permission_classes = [IsAuthenticated, DRYPermissions]
    filter_class = WorkFilter
    search_fields = ('company', 'position')


class ConnectionViewSet(viewsets.ModelViewSet):
    """
    Connection Resource
    """
    queryset = Connection.objects.all()
    serializer_class = ConnectionSerializer
    permission_classes = [IsAuthenticated, DRYObjectPermissions]
    filter_class = ConnectionFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (ConnectionFilterBackend,)
    search_fields = ('from_user__username', 'to_user__username')


class DeveloperApplicationViewSet(viewsets.ModelViewSet):
    """
    Developer Application Resource
    """
    queryset = DeveloperApplication.objects.all()
    serializer_class = DeveloperApplicationSerializer
    permission_classes = [IsAdminOrCreateOnly]
    filter_class = DeveloperApplicationFilter
    filter_backends = DEFAULT_FILTER_BACKENDS
    search_fields = ('first_name', 'last_name')

    @list_route(
        methods=['get'], url_path='key/(?P<key>[^/]+)',
        permission_classes=[AllowAny]
    )
    def get_by_key(self, request, key=None):
        """
        Get application by confirmation key
        """
        try:
            application = get_object_or_404(self.get_queryset(), confirmation_key=key, used=False)
        except ValueError:
            return Response(
                {'status': 'Bad request', 'message': 'Invalid key'},
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer = DeveloperApplicationSerializer(application)
        return Response(serializer.data)


class CountryListView(views.APIView):
    """
    Country Resource
    """
    permission_classes = [AllowAny]

    def get(self, request):
        countries = []
        for country in CountryField().get_choices():
            countries.append({'code': country[0], 'name': country[1]})
        return Response(
            countries,
            status=status.HTTP_200_OK
        )


class NotificationView(views.APIView):
    """
    Notification Resource
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

        new_messages = new_messages_filter(queryset=Message.objects.all(), user=user).count()

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
            {'messages': new_messages, 'requests': requests, 'tasks': tasks, 'profile': profile_notifications},
            status=status.HTTP_200_OK
        )


class RepoListView(views.APIView):
    """
    Repository List Resource
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, provider=None):
        social_token = get_social_token(user=request.user, provider=provider)
        if not social_token:
            return Response({'status': 'Unauthorized'}, status.HTTP_401_UNAUTHORIZED)

        if provider == 'github':
            r = github.api(endpoint='/user/repos', method='get', access_token=social_token.token)
            if r.status_code == 200:
                repos = [extract_repo_info(repo) for repo in r.json()]
                return Response(repos)
            return Response(r.json(), r.status_code)
        return Response({'status': 'Not implemented'}, status.HTTP_501_NOT_IMPLEMENTED)


class IssueListView(views.APIView):
    """
    Issue List Resource
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, provider=None):
        social_token = get_social_token(user=request.user, provider=provider)
        if not social_token:
            return Response({'status': 'Unauthorized'}, status.HTTP_401_UNAUTHORIZED)

        if provider == 'github':
            r = github.api(endpoint='/user/issues', method='get', params={'filter': 'all'}, access_token=social_token.token)
            if r.status_code == 200:
                issues = []
                for issue in r.json():
                    if 'pull_request' in issue:
                        continue  # Github returns both issues and pull requests from this endpoint
                    issue_info = {}
                    for key in ISSUE_FIELDS:
                        if key == 'repository':
                            issue_info[key] = extract_repo_info(issue[key])
                        else:
                            issue_info[key] = issue[key]
                    issues.append(issue_info)
                return Response(issues)
            return Response(r.json(), r.status_code)
        return Response({'status': 'Not implemented'}, status.HTTP_501_NOT_IMPLEMENTED)
