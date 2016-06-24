import django_filters
from django.contrib.contenttypes.models import ContentType

from tunga_comments.models import Comment
from tunga_utils.filters import GenericDateFilterSet
from tunga_tasks.models import Task, TaskRequest


class CommentFilter(GenericDateFilterSet):
    since = django_filters.NumberFilter(name='id', lookup_type='gt')
    task = django_filters.MethodFilter()
    task_request = django_filters.MethodFilter()

    class Meta:
        model = Comment
        fields = ('user', 'content_type', 'object_id', 'since')

    def filter_task(self, queryset, value):
        task_content_type = ContentType.objects.get_for_model(Task)
        return queryset.filter(content_type=task_content_type.id, object_id=value)

    def filter_task_request(self, queryset, value):
        task_request_content_type = ContentType.objects.get_for_model(TaskRequest)
        return queryset.filter(content_type=task_request_content_type.id, object_id=value)

