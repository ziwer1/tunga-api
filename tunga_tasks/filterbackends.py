# -*- coding: utf-8 -*-

import datetime

from dateutil.relativedelta import relativedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db.models.aggregates import Sum
from django.db.models.expressions import Case, When, F
from django.db.models.fields import IntegerField
from django.db.models.query_utils import Q
from dry_rest_permissions.generics import DRYPermissionFiltersBase

from tunga_profiles.models import UserProfile
from tunga_utils.constants import VISIBILITY_DEVELOPER, \
    VISIBILITY_MY_TEAM, TASK_SCOPE_TASK, TASK_SCOPE_ONGOING, TASK_SCOPE_PROJECT, TASK_SOURCE_NEW_USER, STATUS_APPROVED, \
    STATUS_ACCEPTED, STATUS_INITIAL
from tunga_utils.filterbackends import dont_filter_staff_or_superuser


class ProjectFilterBackend(DRYPermissionFiltersBase):
    # @dont_filter_staff_or_superuser
    def filter_list_queryset(self, request, queryset, view):
        queryset = queryset.exclude(archived=True).filter(user=request.user)
        label_filter = request.query_params.get('filter', None)
        if label_filter == 'running':
            queryset = queryset.filter(closed=False)
        return queryset


class TaskFilterBackend(DRYPermissionFiltersBase):
    # @dont_filter_staff_or_superuser
    def filter_list_queryset(self, request, queryset, view):
        label_filter = request.query_params.get('filter', None)
        if label_filter != 'payments':
            queryset = queryset.exclude(archived=True)
        queryset = queryset.filter(user__in=get_user_model().objects.all())

        if label_filter in ['running', 'my-tasks', 'payments']:
            if label_filter == 'running':
                queryset = queryset.filter(closed=False)
            elif label_filter == 'payments':
                queryset = queryset.filter(closed=True).order_by('paid', 'pay_distributed', 'processing', '-created_at')
            if label_filter != 'payments' or not request.user.is_admin:
                queryset = queryset.filter(
                    Q(user=request.user) |
                    Q(owner=request.user) |
                    (
                        Q(participation__user=request.user) & Q(participation__status__in=[STATUS_INITIAL, STATUS_ACCEPTED])
                    )
                )
        elif label_filter in ['new-projects', 'estimates', 'quotes', 'proposals']:
            queryset = queryset.exclude(scope=TASK_SCOPE_TASK)
            if label_filter == 'new-projects':
                queryset = queryset.filter(pm__isnull=True)
            elif label_filter in ['estimates', 'quotes', 'proposals']:
                if request.user.is_project_manager:
                    queryset = queryset.filter(pm=request.user)
                if label_filter in ['estimates', 'proposals']:
                    queryset = queryset.exclude(estimate__status=STATUS_ACCEPTED)
                elif label_filter == 'quotes':
                    queryset = queryset.filter(estimate__status=STATUS_ACCEPTED).exclude(quote__status=STATUS_ACCEPTED)
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
                    Q(user__connections_initiated__status=STATUS_ACCEPTED)
                ) |
                (
                    Q(user__connection_requests__from_user=request.user) &
                    Q(user__connection_requests__status=STATUS_ACCEPTED)
                )
            )

        if request.user.is_authenticated():
            if request.user.is_staff or request.user.is_superuser:
                return queryset
            if request.user.is_project_owner:
                queryset = queryset.filter(Q(user=request.user) | Q(owner=request.user) | Q(taskaccess__user=request.user))
            elif request.user.is_developer:
                return queryset.exclude(
                    approved=False
                ).exclude(
                    ~Q(participation__user=request.user), review=True
                ).filter(
                    Q(scope=TASK_SCOPE_TASK) |
                    (
                        Q(scope=TASK_SCOPE_PROJECT) & Q(pm_required=False) & ~Q(source=TASK_SOURCE_NEW_USER)
                    ) | Q(quote__status=STATUS_ACCEPTED)
                ).filter(
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
                                    Q(user__connection_requests__status=STATUS_ACCEPTED)
                                )
                            )
                        )
                    )
                ).distinct()
            elif request.user.is_project_manager:
                queryset = queryset.filter(
                    Q(user=request.user) |
                    Q(pm=request.user) |
                    Q(taskaccess__user=request.user) | (
                        Q(scope=TASK_SCOPE_ONGOING) |
                        (
                            Q(scope=TASK_SCOPE_PROJECT) & (
                                Q(pm_required=True) | Q(source=TASK_SOURCE_NEW_USER)
                            )
                        )
                    )
                )
            else:
                return queryset.none()
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
                Q(task__participation__status__in=[STATUS_INITIAL, STATUS_ACCEPTED])
            )
        )


class TimeEntryFilterBackend(DRYPermissionFiltersBase):
    @dont_filter_staff_or_superuser
    def filter_list_queryset(self, request, queryset, view):
        return queryset.filter(Q(user=request.user) | Q(task__user=request.user) | Q(task__parent__user=request.user))


class ProgressEventFilterBackend(DRYPermissionFiltersBase):
    # @dont_filter_staff_or_superuser
    def filter_list_queryset(self, request, queryset, view):
        label_filter = request.query_params.get('filter', None)
        threshold_date = datetime.datetime.utcnow() - relativedelta(hours=24)
        if label_filter == 'upcoming':
            queryset = queryset.filter(
                due_at__gt=threshold_date, progressreport__isnull=True
            )
        elif label_filter in ['complete', 'finished']:
            queryset = queryset.filter(
                progressreport__isnull=False
            )
        elif label_filter == 'missed':
            queryset = queryset.filter(
                due_at__lt=threshold_date, progressreport__isnull=True
            )
        if request.user.is_staff or request.user.is_superuser:
            return queryset
        return queryset.filter(
            Q(created_by=request.user) |
            Q(task__user=request.user) |
            (
                Q(task__participation__user=request.user) &
                Q(task__participation__status__in=[STATUS_INITIAL, STATUS_ACCEPTED])
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
                Q(event__task__participation__status__in=[STATUS_INITIAL, STATUS_ACCEPTED])
            )
        )
