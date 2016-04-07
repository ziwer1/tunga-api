from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from tunga_tasks.filters import TaskFilter, ApplicationFilter, ParticipationFilter, TaskRequestFilter, SavedTaskFilter
from tunga_tasks.models import Task, Application, Participation, TaskRequest, SavedTask
from tunga_tasks.serializers import TaskSerializer, ApplicationSerializer, ParticipationSerializer, \
    TaskRequestSerializer, SavedTaskSerializer


class TaskViewSet(viewsets.ModelViewSet):
    """
    Manage Tasks
    """
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]
    filter_class = TaskFilter
    search_fields = ('title', 'description', 'skills__name')


class ApplicationViewSet(viewsets.ModelViewSet):
    """
    Manage Task Applications
    """
    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer
    permission_classes = [IsAuthenticated]
    filter_class = ApplicationFilter
    search_fields = ('task__title', 'task__skills__name', '^user__username', '^user__first_name', '^user__last_name')


class ParticipationViewSet(viewsets.ModelViewSet):
    """
    Manage Task Participation
    """
    queryset = Participation.objects.all()
    serializer_class = ParticipationSerializer
    permission_classes = [IsAuthenticated]
    filter_class = ParticipationFilter
    search_fields = ('task__title', 'task__skills__name', '^user__username', '^user__first_name', '^user__last_name')


class TaskRequestViewSet(viewsets.ModelViewSet):
    """
    Manage Task Requests
    """
    queryset = TaskRequest.objects.all()
    serializer_class = TaskRequestSerializer
    permission_classes = [IsAuthenticated]
    filter_class = TaskRequestFilter
    search_fields = ('task__title', 'task__skills__name', '^user__username', '^user__first_name', '^user__last_name')


class SavedTaskViewSet(viewsets.ModelViewSet):
    """
    Manage Saved Tasks
    """
    queryset = SavedTask.objects.all()
    serializer_class = SavedTaskSerializer
    permission_classes = [IsAuthenticated]
    filter_class = SavedTaskFilter
    search_fields = ('task__title', 'task__skills__name', '^user__username', '^user__first_name', '^user__last_name')
