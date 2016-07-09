from django.core.exceptions import ObjectDoesNotExist
from django.db.models.aggregates import Count, Sum
from django.db.models.expressions import Case, When
from django.db.models.fields import IntegerField
from django.db.models.query_utils import Q
from dry_rest_permissions.generics import DRYPermissionFiltersBase
from tunga_auth.models import USER_TYPE_DEVELOPER, USER_TYPE_PROJECT_OWNER
from tunga_profiles.models import UserProfile
from tunga_settings.models import VISIBILITY_DEVELOPER, VISIBILITY_MY_TEAM, VISIBILITY_CUSTOM
from tunga_utils.filterbackends import dont_filter_staff_or_superuser


class ProjectFilterBackend(DRYPermissionFiltersBase):
    # @dont_filter_staff_or_superuser
    def filter_list_queryset(self, request, queryset, view):
        queryset = queryset.filter(user=request.user)
        label_filter = request.query_params.get('filter', None)
        if label_filter == 'running':
            queryset = queryset.filter(closed=False)
        return queryset


class TaskFilterBackend(DRYPermissionFiltersBase):
    # @dont_filter_staff_or_superuser
    def filter_list_queryset(self, request, queryset, view):
        label_filter = request.query_params.get('filter', None)
        if label_filter in ['running', 'my-tasks']:
            if label_filter == 'running':
                queryset = queryset.filter(closed=False)
            queryset = queryset.filter(
                Q(user=request.user) |
                (
                    Q(participation__user=request.user) &
                    (
                        Q(participation__accepted=True) | Q(participation__responded=False)
                    )
                )
            )
        elif label_filter == 'saved':
            queryset = queryset.filter(savedtask__user=request.user)
        elif label_filter == 'skills':
            try:
                user_skills = request.user.userprofile.skills.all()
                queryset = queryset.filter(skills__in=user_skills)
                when = []
                for skill in user_skills:
                    new_when = When(
                        skills=skill,
                        then=1
                    )
                    when.append(new_when)
                queryset = queryset.annotate(matches=Sum(
                    Case(
                        *when,
                        default=0,
                        output_field=IntegerField()
                    )
                )).order_by('-matches', '-created_at')
            except (ObjectDoesNotExist, UserProfile.DoesNotExist):
                return queryset.none()
        elif label_filter in ['my-clients', 'project-owners']:
            queryset = queryset.filter(
                (
                    Q(user__connections_initiated__to_user=request.user) &
                    Q(user__connections_initiated__accepted=True)
                ) |
                (
                    Q(user__connection_requests__from_user=request.user) &
                    Q(user__connection_requests__accepted=True)
                )
            )

        if request.user.is_staff or request.user.is_superuser:
            return queryset
        if request.user.type == USER_TYPE_PROJECT_OWNER:
            queryset = queryset.filter(user=request.user)
        elif request.user.type == USER_TYPE_DEVELOPER:
            return queryset.filter(
                Q(user=request.user) |
                Q(participation__user=request.user) |
                (
                    Q(visibility=VISIBILITY_DEVELOPER) |
                    (
                        Q(visibility=VISIBILITY_MY_TEAM) &
                        (
                            (
                                Q(user__connections_initiated__to_user=request.user) &
                                Q(user__connections_initiated__accepted=True)
                            ) |
                            (
                                Q(user__connection_requests__from_user=request.user) &
                                Q(user__connection_requests__accepted=True)
                            )
                        )
                    )
                )
            ).distinct()
        else:
            return queryset.none()
        return queryset


class ApplicationFilterBackend(DRYPermissionFiltersBase):
    @dont_filter_staff_or_superuser
    def filter_list_queryset(self, request, queryset, view):
        return queryset.filter(Q(user=request.user) | Q(task__user=request.user))


class ParticipationFilterBackend(DRYPermissionFiltersBase):
    @dont_filter_staff_or_superuser
    def filter_list_queryset(self, request, queryset, view):
        return queryset.filter(
            Q(user=request.user) |
            Q(task__user=request.user) |
            (
                Q(task__participation__user=request.user) &
                (
                    Q(task__participation__accepted=True) | Q(task__participation__responded=False)
                )
            )
        )


class TaskRequestFilterBackend(DRYPermissionFiltersBase):
    @dont_filter_staff_or_superuser
    def filter_list_queryset(self, request, queryset, view):
        return queryset.filter(
            Q(user=request.user) |
            Q(task__user=request.user) |
            (
                Q(task__participation__user=request.user) &
                (
                    Q(task__participation__accepted=True) | Q(task__participation__responded=False)
                )
            )
        )


class SavedTaskFilterBackend(DRYPermissionFiltersBase):
    @dont_filter_staff_or_superuser
    def filter_list_queryset(self, request, queryset, view):
        return queryset.filter(user=request.user)


class ProgressEventFilterBackend(DRYPermissionFiltersBase):
    @dont_filter_staff_or_superuser
    def filter_list_queryset(self, request, queryset, view):
        return queryset.filter(
            Q(created_by=request.user) |
            Q(task__user=request.user) |
            (
                Q(task__participation__user=request.user) &
                (
                    Q(task__participation__accepted=True) | Q(task__participation__responded=False)
                )
            )
        )


class ProgressReportFilterBackend(DRYPermissionFiltersBase):
    @dont_filter_staff_or_superuser
    def filter_list_queryset(self, request, queryset, view):
        return queryset.filter(
            Q(user=request.user) |
            Q(event__task__user=request.user) |
            (
                Q(event__task__participation__user=request.user) &
                (
                    Q(event__task__participation__accepted=True) | Q(event__task__participation__responded=False)
                )
            )
        )
