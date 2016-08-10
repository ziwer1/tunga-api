from django.core.exceptions import ObjectDoesNotExist
from django.db.models.aggregates import Count, Sum
from django.db.models.expressions import When, Case
from django.db.models.fields import IntegerField
from django.db.models.query_utils import Q
from dry_rest_permissions.generics import DRYPermissionFiltersBase

from tunga_auth.models import USER_TYPE_DEVELOPER, USER_TYPE_PROJECT_OWNER
from tunga_profiles.models import UserProfile


def my_connections_q_filter(user):
    return (
        (
            Q(connections_initiated__to_user=user) &
            Q(connections_initiated__accepted=True)
        ) |
        (
            Q(connection_requests__from_user=user) &
            Q(connection_requests__accepted=True)
        )
    )


class UserFilterBackend(DRYPermissionFiltersBase):

    def filter_list_queryset(self, request, queryset, view):
        if view.action == 'list':
            queryset = queryset.exclude(id=request.user.id)
        queryset = queryset.exclude(pending=True)
        user_filter = request.query_params.get('filter', None)
        if user_filter == 'developers':
            queryset = queryset.filter(type=USER_TYPE_DEVELOPER)
        elif user_filter in ['project-owners', 'clients']:
            queryset = queryset.filter(type=USER_TYPE_PROJECT_OWNER)
        elif user_filter in ['team', 'my-project-owners', 'my-clients']:
            if user_filter in ['my-project-owners', 'my-clients']:
                user_type = USER_TYPE_PROJECT_OWNER
            else:
                user_type = USER_TYPE_DEVELOPER
            queryset = queryset.filter(type=user_type).filter(
                my_connections_q_filter(request.user)
            )
        elif user_filter == 'requests':
            queryset = queryset.filter(
                connections_initiated__to_user=request.user, connections_initiated__responded=False)
        elif user_filter == 'relevant':
            queryset = queryset.filter(type=USER_TYPE_DEVELOPER)
            try:
                user_skills = request.user.userprofile.skills.all()
                queryset = queryset.filter(userprofile__skills__in=user_skills)
                when = []
                for skill in user_skills:
                    new_when = When(
                            userprofile__skills=skill,
                            then=1
                        )
                    when.append(new_when)
                queryset = queryset.annotate(matches=Sum(
                    Case(
                        *when,
                        default=0,
                        output_field=IntegerField()
                    )
                )).order_by('-matches', '-date_joined')
            except (ObjectDoesNotExist, UserProfile.DoesNotExist):
                return queryset.none()
        return queryset
