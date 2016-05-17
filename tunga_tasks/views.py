import json

from django.shortcuts import render, redirect
from dry_rest_permissions.generics import DRYObjectPermissions
from rest_framework import viewsets
from rest_framework.decorators import detail_route
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from tunga_tasks.filterbackends import TaskFilterBackend
from tunga_tasks.filters import TaskFilter, ApplicationFilter, ParticipationFilter, TaskRequestFilter, SavedTaskFilter
from tunga_tasks.models import Task, Application, Participation, TaskRequest, SavedTask
from tunga_tasks.serializers import TaskSerializer, ApplicationSerializer, ParticipationSerializer, \
    TaskRequestSerializer, SavedTaskSerializer
from tunga_utils.filterbackends import DEFAULT_FILTER_BACKENDS


class TaskViewSet(viewsets.ModelViewSet):
    """
    Task Resource
    """
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated, DRYObjectPermissions]
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
    permission_classes = [IsAuthenticated]
    filter_class = ApplicationFilter
    search_fields = ('task__title', 'task__skills__name', '^user__username', '^user__first_name', '^user__last_name')


class ParticipationViewSet(viewsets.ModelViewSet):
    """
    Task Participation Resource
    """
    queryset = Participation.objects.all()
    serializer_class = ParticipationSerializer
    permission_classes = [IsAuthenticated]
    filter_class = ParticipationFilter
    search_fields = ('task__title', 'task__skills__name', '^user__username', '^user__first_name', '^user__last_name')


class TaskRequestViewSet(viewsets.ModelViewSet):
    """
    Task Request Resource
    """
    queryset = TaskRequest.objects.all()
    serializer_class = TaskRequestSerializer
    permission_classes = [IsAuthenticated]
    filter_class = TaskRequestFilter
    search_fields = ('task__title', 'task__skills__name', '^user__username', '^user__first_name', '^user__last_name')


class SavedTaskViewSet(viewsets.ModelViewSet):
    """
    Saved Task Resource
    """
    queryset = SavedTask.objects.all()
    serializer_class = SavedTaskSerializer
    permission_classes = [IsAuthenticated]
    filter_class = SavedTaskFilter
    search_fields = ('task__title', 'task__skills__name', '^user__username', '^user__first_name', '^user__last_name')


def task_webscrapers(request, pk=None):
    try:
        task = Task.objects.get(id=pk)
        participation = json.dumps(task.meta_participation)
        payment_meta = task.meta_payment
        payment_meta['task_url'] = '%s://%s%s' % (request.scheme, request.get_host(), payment_meta['task_url'])
        payment = json.dumps(payment_meta)
        return render(request, 'tunga/index.html', {'task': task, 'participation': participation, 'payment': payment})
    except (Task.DoesNotExist, Task.MultipleObjectsReturned):
        return redirect('/task/')
