import django_filters

from tunga_tasks.models import Task, Application, Participation, TaskRequest, SavedTask
from tunga_utils.filters import GenericDateFilterSet


class TaskFilter(GenericDateFilterSet):
    applicant = django_filters.NumberFilter(name='applications__user', label='Applicant')
    participant = django_filters.NumberFilter(name='participants__user', label='Participant')

    class Meta:
        model = Task
        fields = ('user', 'closed', 'applicant', 'participant', 'paid')


class ApplicationFilter(GenericDateFilterSet):
    class Meta:
        model = Application
        fields = ('user', 'task', 'accepted', 'responded')


class ParticipationFilter(GenericDateFilterSet):
    class Meta:
        model = Participation
        fields = ('user', 'task', 'accepted')


class TaskRequestFilter(GenericDateFilterSet):
    class Meta:
        model = TaskRequest
        fields = ('user', 'task', 'type')


class SavedTaskFilter(GenericDateFilterSet):
    class Meta:
        model = SavedTask
        fields = ('user', 'task')
