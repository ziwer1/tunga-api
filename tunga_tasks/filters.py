import django_filters

from tunga_tasks.models import Task, Application, Participation, TimeEntry, Project, ProgressReport, ProgressEvent, \
    Estimate, Quote, TaskPayment, ParticipantPayment
from tunga_utils.constants import TASK_PAYMENT_METHOD_STRIPE
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
            request = self.request
            is_po = request and request.user and request.user.is_authenticated() and request.user.is_project_owner and not request.user.is_admin
            if value == 'processing':
                return queryset.filter(processing=True, paid=False)
            if value == 'paid':
                return is_po and queryset or queryset.filter(pay_distributed=True)
            else:
                return queryset.filter(pay_distributed=False)
        elif value == 'pending':
            queryset = queryset.filter(processing=False, paid=False)
        elif value == 'distribute':
            queryset = queryset.filter(
                payment_method=TASK_PAYMENT_METHOD_STRIPE,
                paid=True, btc_paid=False, pay_distributed=False
            )
        return queryset


class ApplicationFilter(GenericDateFilterSet):
    class Meta:
        model = Application
        fields = ('user', 'task', 'status')


class ParticipationFilter(GenericDateFilterSet):
    class Meta:
        model = Participation
        fields = ('user', 'task', 'status')


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


class TaskPaymentFilter(GenericDateFilterSet):
    user = django_filters.NumberFilter(name='task_user')
    owner = django_filters.NumberFilter(name='task_owner')

    class Meta:
        model = TaskPayment
        fields = ('task', 'ref', 'payment_type', 'btc_address', 'processed', 'paid', 'captured', 'user', 'owner')


class ParticipantPaymentFilter(GenericDateFilterSet):
    user = django_filters.NumberFilter(name='participant__user')
    task = django_filters.NumberFilter(name='source__task')

    class Meta:
        model = ParticipantPayment
        fields = ('participant', 'source', 'destination', 'ref', 'idem_key', 'status', 'user', 'task')