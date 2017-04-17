import json

from allauth.socialaccount.providers.github.provider import GitHubProvider
from django.db.models.query_utils import Q
from django.shortcuts import get_object_or_404
from django.utils import six
from django_countries.fields import CountryField
from dry_rest_permissions.generics import DRYObjectPermissions, DRYPermissions
from rest_framework import viewsets, generics, views, status
from rest_framework.decorators import list_route
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.response import Response
from slacker import Slacker

from tunga_auth.permissions import IsAdminOrCreateOnly
from tunga_messages.models import Channel
from tunga_messages.utils import channel_new_messages_filter
from tunga_profiles.filterbackends import ConnectionFilterBackend
from tunga_profiles.filters import EducationFilter, WorkFilter, ConnectionFilter, DeveloperApplicationFilter, \
    DeveloperInvitationFilter
from tunga_profiles.models import UserProfile, Education, Work, Connection, DeveloperApplication, DeveloperInvitation
from tunga_profiles.serializers import ProfileSerializer, EducationSerializer, WorkSerializer, ConnectionSerializer, \
    DeveloperApplicationSerializer, DeveloperInvitationSerializer
from tunga_tasks.models import Task
from tunga_tasks.utils import get_integration_token
from tunga_utils import github, harvest_utils, slack_utils
from tunga_utils.constants import USER_TYPE_PROJECT_OWNER, APP_INTEGRATION_PROVIDER_SLACK, CHANNEL_TYPE_SUPPORT, \
    CHANNEL_TYPE_DIRECT, CHANNEL_TYPE_TOPIC, CHANNEL_TYPE_DEVELOPER, APP_INTEGRATION_PROVIDER_HARVEST, \
    TASK_SCOPE_ONGOING, TASK_SCOPE_PROJECT, TASK_SOURCE_NEW_USER, STATUS_ACCEPTED, STATUS_INITIAL, STATUS_REJECTED
from tunga_utils.filterbackends import DEFAULT_FILTER_BACKENDS


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


class DeveloperInvitationViewSet(viewsets.ModelViewSet):
    """
    Developer Application Resource
    """
    queryset = DeveloperInvitation.objects.all()
    serializer_class = DeveloperInvitationSerializer
    permission_classes = [IsAdminUser]
    filter_class = DeveloperInvitationFilter
    filter_backends = DEFAULT_FILTER_BACKENDS
    search_fields = ('first_name', 'last_name')

    @list_route(
        methods=['get'], url_path='key/(?P<key>[^/]+)',
        permission_classes=[AllowAny]
    )
    def get_by_key(self, request, key=None):
        """
        Get application by invitation key
        """
        try:
            application = get_object_or_404(self.get_queryset(), invitation_key=key, used=False)
        except ValueError:
            return Response(
                {'status': 'Bad request', 'message': 'Invalid key'},
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer = DeveloperInvitationSerializer(application)
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

        channel_filter = Q(channeluser__user=user)
        if user.is_staff and user.is_superuser or user.is_developer:
            # channel_filter = channel_filter | Q(type=CHANNEL_TYPE_DEVELOPER)
            # TODO: Channel filter should include all developer channels for admins and devs
            # However enabling above query currently breaks new message counts
            pass

        channels_with_messages = channel_new_messages_filter(
            Channel.objects.filter(channel_filter),
            user=user
        )

        channel_updates = [
            dict(id=channel.id, type=channel.type, new=channel.new_messages, last_read=channel.channel_last_read)
            for channel in channels_with_messages]

        channel_type_map = {
            CHANNEL_TYPE_DIRECT: 'direct',
            CHANNEL_TYPE_TOPIC: 'topic',
            CHANNEL_TYPE_SUPPORT: 'support',
            CHANNEL_TYPE_DEVELOPER: 'developer'
        }

        channel_type_summary_updates = dict()
        for channel_type_name in six.itervalues(channel_type_map):
            channel_type_summary_updates[channel_type_name] = 0

        for channel in channel_updates:
            channel_type_summary_updates[channel_type_map.get(channel['type'], '')] += channel['new']

        requests = user.connection_requests.filter(status=STATUS_INITIAL, from_user__pending=False).count()
        tasks = user.tasks_created.filter(closed=False).count() + user.participation_set.exclude(
            status=STATUS_REJECTED).filter(
            task__closed=False, user=user
        ).count() + user.tasks_managed.filter(closed=False).count()
        pm_tasks = Task.objects.filter(
            Q(scope=TASK_SCOPE_ONGOING) |
            (
                Q(scope=TASK_SCOPE_PROJECT) & (
                    Q(pm_required=True) | Q(source=TASK_SOURCE_NEW_USER)
                )
            )
        )
        if request.user.is_project_manager:
            pm_tasks.filter(pm=request.user)
        estimates = pm_tasks.exclude(estimate__status=STATUS_ACCEPTED).distinct().count()
        quotes = pm_tasks.filter(estimate__status=STATUS_ACCEPTED).exclude(quote__status=STATUS_ACCEPTED).distinct().count()

        profile = None
        profile_notifications = {'count': 0, 'missing': [], 'improve': [], 'more': [], 'section': None}
        try:
            profile = user.userprofile
        except:
            profile_notifications['missing'] = ['skills', 'bio', 'country', 'city', 'street', 'plot_number',
                                                'phone_number']

        if not user.avatar_url:
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
            {
                'messages': channel_type_summary_updates['direct'] + channel_type_summary_updates['topic'] + channel_type_summary_updates['developer'],
                'requests': requests,
                'tasks': tasks,
                'estimates': estimates,
                'quotes': quotes,
                'profile': profile_notifications,
                'channels': channel_updates,
                'channel_summary': channel_type_summary_updates
            },
            status=status.HTTP_200_OK
        )


class RepoListView(views.APIView):
    """
    Repository List Resource
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, provider=None):
        social_token = get_integration_token(request.user, provider, task=request.GET.get('task'))
        if not social_token:
            return Response({'status': 'Unauthorized'}, status.HTTP_401_UNAUTHORIZED)

        if provider == GitHubProvider.id:
            r = github.api(endpoint='/user/repos', method='get', access_token=social_token.token)
            if r.status_code == 200:
                repos = [github.extract_repo_info(repo) for repo in r.json()]
                return Response(repos)
            return Response(r.json(), r.status_code)
        return Response({'status': 'Not implemented'}, status.HTTP_501_NOT_IMPLEMENTED)


class IssueListView(views.APIView):
    """
    Issue List Resource
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, provider=None):
        social_token = get_integration_token(request.user, provider, task=request.GET.get('task'))
        if not social_token:
            return Response({'status': 'Unauthorized'}, status.HTTP_401_UNAUTHORIZED)

        if provider == GitHubProvider.id:
            r = github.api(endpoint='/user/issues', method='get', params={'filter': 'all'},
                           access_token=social_token.token)
            if r.status_code == 200:
                issues = []
                for issue in r.json():
                    if 'pull_request' in issue:
                        continue  # Github returns both issues and pull requests from this endpoint
                    issue_info = {}
                    for key in github.ISSUE_FIELDS:
                        if key == 'repository':
                            issue_info[key] = github.extract_repo_info(issue[key])
                        else:
                            issue_info[key] = issue[key]
                    issues.append(issue_info)
                return Response(issues)
            return Response(r.json(), r.status_code)
        return Response({'status': 'Not implemented'}, status.HTTP_501_NOT_IMPLEMENTED)


class SlackIntegrationView(views.APIView):
    """
    Slack App Integration Info Resource
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, resource=None):
        app_integration = get_integration_token(
            request.user, APP_INTEGRATION_PROVIDER_SLACK, task=request.GET.get('task')
        )
        if app_integration and app_integration.extra:
            extra = json.loads(app_integration.extra)
            slack_client = Slacker(app_integration.token)
            response = None
            if resource == 'channels':
                channel_response = slack_client.channels.list(exclude_archived=True)
                if channel_response.successful:
                    response = channel_response.body.get(slack_utils.KEY_CHANNELS, None)
            else:
                response = {
                    'team': {'name': extra.get('team_name'), 'id': extra.get('team_id', None)},
                    # 'incoming_webhook': {'channel': extra.get('incoming_webhook').get('channel')}
                }
            if response:
                return Response(response, status.HTTP_200_OK)
            return Response({'status': 'Failed'}, status.HTTP_400_BAD_REQUEST)

        return Response({'status': 'Not implemented'}, status.HTTP_501_NOT_IMPLEMENTED)


class HarvestAPIView(views.APIView):
    """
    Harvest API Resource
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, resource=None):
        app_integration = get_integration_token(
            request.user, APP_INTEGRATION_PROVIDER_HARVEST, task=request.GET.get('task')
        )
        if app_integration and app_integration.extra:
            token = json.loads(app_integration.extra)

            response = None
            harvest_client = harvest_utils.get_api_client(token, user=request.user)

            if resource == 'projects':
                response = harvest_client.projects()
            elif resource == 'tasks':
                project_id = request.query_params.get('project', None)
                if project_id:
                    response = harvest_client.get_all_tasks_from_project(project_id)
                else:
                    response = harvest_client.tasks()
            elif resource == 'task_assignments':
                project_id = request.query_params.get('project', None)
                if project_id:
                    response = harvest_client.get_all_tasks_from_project(project_id)
            return Response(
                response and response.json() or {'status': 'Failed'},
                response and response.status_code or status.HTTP_400_BAD_REQUEST
            )

        return Response({'status': 'Not implemented'}, status.HTTP_501_NOT_IMPLEMENTED)

    def post(self, request, resource=None):
        app_integration = get_integration_token(request.user, APP_INTEGRATION_PROVIDER_HARVEST, task=request.GET.get('task'))
        if app_integration and app_integration.extra:
            token = json.loads(app_integration.extra)
            response = None
            harvest_client = harvest_utils.get_api_client(token, user=request.user)

            if resource == 'users':
                harvest_client.create_user(request.data)
            elif resource == 'entries':
                harvest_client.add(request.data)
            elif resource == 'projects':
                harvest_client.create_project(**request.data)
            elif resource == 'tasks':
                project_id = request.query_params.get('project', None)
                if project_id:
                    harvest_client.create_task_to_project(project_id, **request.data)
                else:
                    harvest_client.create_task(**request.data)

                    return Response(
                        response and response.json() or {'status': 'Failed'},
                        response and response.status_code or status.HTTP_400_BAD_REQUEST
                    )

        return Response({'status': 'Not implemented'}, status.HTTP_501_NOT_IMPLEMENTED)
