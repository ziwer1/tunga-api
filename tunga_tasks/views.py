import json

from django.shortcuts import render, redirect
from dry_rest_permissions.generics import DRYPermissions, DRYObjectPermissions
from rest_framework import viewsets
from rest_framework.decorators import detail_route
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from tunga_tasks.filterbackends import TaskFilterBackend, ApplicationFilterBackend, ParticipationFilterBackend, \
    TaskRequestFilterBackend, SavedTaskFilterBackend, ProjectFilterBackend, ProgressReportFilterBackend, \
    ProgressEventFilterBackend
from tunga_tasks.filters import TaskFilter, ApplicationFilter, ParticipationFilter, TaskRequestFilter, SavedTaskFilter, \
    ProjectFilter, ProgressReportFilter, ProgressEventFilter
from tunga_tasks.models import Task, Application, Participation, TaskRequest, SavedTask, Project, ProgressReport, ProgressEvent, \
    PROGRESS_EVENT_TYPE_MILESTONE
from tunga_tasks.serializers import TaskSerializer, ApplicationSerializer, ParticipationSerializer, \
    TaskRequestSerializer, SavedTaskSerializer, ProjectSerializer, ProgressReportSerializer, ProgressEventSerializer
from tunga_utils.filterbackends import DEFAULT_FILTER_BACKENDS
from tunga_utils.mixins import SaveUploadsMixin


class ProjectViewSet(viewsets.ModelViewSet):
    """
    Project Resource
    """
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated, DRYPermissions]
    filter_class = ProjectFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (ProjectFilterBackend,)
    search_fields = ('title', 'description')


class TaskViewSet(viewsets.ModelViewSet, SaveUploadsMixin):
    """
    Task Resource
    """
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated, DRYPermissions]
    filter_class = TaskFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (TaskFilterBackend,)
    search_fields = ('title', 'description', 'skills__name')

    @detail_route(
        methods=['get'], url_path='meta',
        permission_classes=[IsAuthenticated]
    )
    def meta(self, request, pk=None):
        """
        Get task meta data
        """
        task = get_object_or_404(self.get_queryset(), pk=pk)
        self.check_object_permissions(request, task)

        participation = json.dumps(task.meta_participation)
        payment_meta = task.meta_payment
        payment_meta['task_url'] = '%s://%s%s' % (request.scheme, request.get_host(), payment_meta['task_url'])
        payment = json.dumps(payment_meta)
        return Response({'task': task.id, 'participation': participation, 'payment': payment})


class ApplicationViewSet(viewsets.ModelViewSet):
    """
    Task Application Resource
    """
    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer
    permission_classes = [IsAuthenticated, DRYPermissions]
    filter_class = ApplicationFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (ApplicationFilterBackend,)
    search_fields = ('task__title', 'task__skills__name', '^user__username', '^user__first_name', '^user__last_name')


class ParticipationViewSet(viewsets.ModelViewSet):
    """
    Task Participation Resource
    """
    queryset = Participation.objects.all()
    serializer_class = ParticipationSerializer
    permission_classes = [IsAuthenticated, DRYObjectPermissions]
    filter_class = ParticipationFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (ParticipationFilterBackend,)
    search_fields = ('task__title', 'task__skills__name', '^user__username', '^user__first_name', '^user__last_name')


class TaskRequestViewSet(viewsets.ModelViewSet):
    """
    Task Request Resource
    """
    queryset = TaskRequest.objects.all()
    serializer_class = TaskRequestSerializer
    permission_classes = [IsAuthenticated, DRYPermissions]
    filter_class = TaskRequestFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (TaskRequestFilterBackend,)
    search_fields = ('task__title', 'task__skills__name', '^user__username', '^user__first_name', '^user__last_name')


class SavedTaskViewSet(viewsets.ModelViewSet):
    """
    Saved Task Resource
    """
    queryset = SavedTask.objects.all()
    serializer_class = SavedTaskSerializer
    permission_classes = [IsAuthenticated, DRYPermissions]
    filter_class = SavedTaskFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (SavedTaskFilterBackend,)
    search_fields = ('task__title', 'task__skills__name', '^user__username', '^user__first_name', '^user__last_name')


class ProgressEventViewSet(viewsets.ModelViewSet):
    """
    Progress Event Resource
    """
    queryset = ProgressEvent.objects.filter(type=PROGRESS_EVENT_TYPE_MILESTONE)
    serializer_class = ProgressEventSerializer
    permission_classes = [IsAuthenticated, DRYPermissions]
    filter_class = ProgressEventFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (ProgressEventFilterBackend,)
    search_fields = (
        'title', 'description', 'task__title', 'task__skills__name',
        '^created_by__user__username', '^created_by__user__first_name', '^created_by__user__last_name',
    )


class ProgressReportViewSet(viewsets.ModelViewSet):
    """
    Progress Report Resource
    """
    queryset = ProgressReport.objects.all()
    serializer_class = ProgressReportSerializer
    permission_classes = [IsAuthenticated, DRYPermissions]
    filter_class = ProgressReportFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (ProgressReportFilterBackend,)
    search_fields = (
        '^user__username', '^user__first_name', '^user__last_name', 'accomplished', 'next_steps', 'remarks',
        'event__task__title', 'event__task__skills__name'
    )


def task_web_view(request, pk=None):
    try:
        task = Task.objects.get(id=pk)
        participation = json.dumps(task.meta_participation)
        payment_meta = task.meta_payment
        payment_meta['task_url'] = '%s://%s%s' % (request.scheme, request.get_host(), payment_meta['task_url'])
        payment = json.dumps(payment_meta)
        return render(request, 'tunga/index.html', {'task': task, 'participation': participation, 'payment': payment})
    except (Task.DoesNotExist, Task.MultipleObjectsReturned):
        return redirect('/task/')
