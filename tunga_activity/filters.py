import django_filters
from actstream.models import Action
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from tunga_tasks.models import Task
from tunga_utils.filters import GenericDateFilterSet


class ActionFilter(GenericDateFilterSet):
    user = django_filters.MethodFilter()
    task = django_filters.MethodFilter()

    class Meta:
        model = Action
        fields = (
            'verb', 'actor_content_type', 'actor_object_id', 'target_content_type', 'target_object_id',
            'action_object_content_type', 'action_object_object_id'
        )

    def filter_user(self, queryset, value):
        user_content_type = ContentType.objects.get_for_model(get_user_model())
        return queryset.filter(actor_content_type=user_content_type.id, actor_object_id=value)

    def filter_task(self, queryset, value):
        task_content_type = ContentType.objects.get_for_model(Task)
        return queryset.filter(target_content_type=task_content_type.id, target_object_id=value)


