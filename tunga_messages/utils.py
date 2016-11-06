from django.db.models import Q, Case, When, IntegerField, F
from django.db.models.aggregates import Sum, Max
from django.db.models.fields import DateTimeField

from tunga_activity import verbs


def all_messages_q_filter(user):
    return Q(user=user) | Q(channel__channeluser__user=user)


def channel_last_read_annotation(user):
    return Case(
        When(
            channeluser__user=user,
            then='channeluser__last_read'
        ),
        default=0,
        output_field=IntegerField()
    )


def channel_activity_last_read_annotation(user):
    return Case(
        When(
            channels__channeluser__user=user,
            then='channels__channeluser__last_read'
        ),
        default=0,
        output_field=IntegerField()
    )


def channel_new_messages_annotation(user):
    """
    Queryset needs to annotated with channel_last_read for this to work
    :param user:
    :return:
    """
    return Sum(
        Case(
            When(
                ~Q(action_targets__actor_object_id=user.id) &
                Q(action_targets__gt=F('channel_last_read')) &
                Q(action_targets__verb__in=[verbs.SEND, verbs.UPLOAD]),
                then=1
            ),
            default=0,
            output_field=IntegerField()
        )
    )


def annotate_channel_queryset_with_new_messages(queryset, user):
    return queryset.annotate(
        channel_last_read=channel_last_read_annotation(user)
    ).annotate(
        new_messages=channel_new_messages_annotation(user)
    )


def annotate_channel_queryset_with_latest_activity_at(queryset, user):
    return queryset.annotate(
        latest_activity_timestamp=Max('action_targets__timestamp'),
    ).annotate(
        latest_activity_at=Case(
            When(
                latest_activity_timestamp__isnull=True,
                then='created_at'
            ),
            When(
                latest_activity_timestamp__gt=F('created_at'),
                then='latest_activity_timestamp'
            ),
            default='created_at',
            output_field=DateTimeField()
        )
    )


def channel_new_messages_filter(queryset, user):
    return annotate_channel_queryset_with_new_messages(
        queryset, user
    ).filter(new_messages__gt=0)


def channel_activity_new_messages_filter(queryset, user):
    return queryset.filter(
        ~Q(actor_object_id=user.id) &
        Q(verb__in=[verbs.SEND, verbs.UPLOAD])
    ).annotate(
        channel_last_read=channel_activity_last_read_annotation(user)
    ).filter(
        id__gt=F('channel_last_read')
    )
