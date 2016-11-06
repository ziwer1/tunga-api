import django_filters
from actstream.models import Action
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from tunga_activity import verbs
from tunga_tasks.models import Task
from tunga_utils.filters import GenericDateFilterSet


class ActionFilter(GenericDateFilterSet):
    user = django_filters.MethodFilter()
    task = django_filters.MethodFilter()
    since = django_filters.NumberFilter(name='id', lookup_type='gt')

    class Meta:
        model = Action
        fields = (
            'verb', 'actor_content_type', 'actor_object_id', 'target_content_type', 'target_object_id',
            'action_object_content_type', 'action_object_object_id', 'since'
        )

    def filter_user(self, queryset, value):
        return queryset.filter(
            actor_content_type=ContentType.objects.get_for_model(get_user_model()), actor_object_id=value
        )

    def filter_task(self, queryset, value):
        return queryset.filter(
            target_content_type=ContentType.objects.get_for_model(Task), target_object_id=value
        )


class MessageActivityFilter(ActionFilter):
    since = django_filters.MethodFilter()

    def filter_since(self, queryset, value):
        return queryset.filter(
            id__gt=value, verb__in=[verbs.SEND, verbs.UPLOAD]
        )
