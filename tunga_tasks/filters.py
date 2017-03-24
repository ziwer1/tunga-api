import django_filters

from tunga_tasks.models import Task, Application, Participation, TimeEntry, Project, ProgressReport, ProgressEvent, \
    Estimate, Quote
from tunga_utils.filters import GenericDateFilterSet


class ProjectFilter(GenericDateFilterSet):

    class Meta:
        model = Project
        fields = ('user', 'closed')


class TaskFilter(GenericDateFilterSet):
    applicant = django_filters.NumberFilter(name='applications__user', label='Applicant')
    participant = django_filters.NumberFilter(name='participants__user', label='Participant')
    payment_status = django_filters.CharFilter(method='filter_payment_status')
    skill = django_filters.CharFilter(name='skills__name', label='skills')
    skill_id = django_filters.NumberFilter(name='skills', label='skills (by ID)')

    class Meta:
        model = Task
        fields = (
            'user', 'project', 'parent', 'type', 'scope', 'source', 'closed', 'applicant', 'participant',
            'paid', 'pay_distributed', 'payment_status',
            'skill', 'skill_id'
        )

    def filter_payment_status(self, queryset, name, value):
        queryset = queryset.filter(closed=True)
        if value in ['paid', 'processing']:
            queryset = queryset.filter(paid=True)
            if value == 'paid':
                return queryset.filter(pay_distributed=True)
            else:
                return queryset.filter(pay_distributed=False)
        elif value == 'pending':
            queryset = queryset.filter(paid=False)
        return queryset


class ApplicationFilter(GenericDateFilterSet):
    class Meta:
        model = Application
        fields = ('user', 'task', 'accepted', 'responded')


class ParticipationFilter(GenericDateFilterSet):
    class Meta:
        model = Participation
        fields = ('user', 'task', 'accepted')


class EstimateFilter(GenericDateFilterSet):

    class Meta:
        model = Estimate
        fields = ('user', 'task', 'status', 'moderated_by')


class QuoteFilter(GenericDateFilterSet):

    class Meta:
        model = Quote
        fields = ('user', 'task', 'status', 'moderated_by')


class TimeEntryFilter(GenericDateFilterSet):
    min_date = django_filters.IsoDateTimeFilter(name='spent_at', lookup_expr='gte')
    max_date = django_filters.IsoDateTimeFilter(name='spent_at', lookup_expr='lte')
    min_hours = django_filters.IsoDateTimeFilter(name='hours', lookup_expr='gte')
    max_hours = django_filters.IsoDateTimeFilter(name='hours', lookup_expr='lte')

    class Meta:
        model = TimeEntry
        fields = ('user', 'task', 'spent_at', 'hours')


class ProgressEventFilter(GenericDateFilterSet):

    class Meta:
        model = ProgressEvent
        fields = ('created_by', 'task', 'type')


class ProgressReportFilter(GenericDateFilterSet):
    task = django_filters.NumberFilter(name='event__task')
    event_type = django_filters.NumberFilter(name='event__type')

    class Meta:
        model = ProgressReport
        fields = ('user', 'event', 'task', 'event_type', 'status')
