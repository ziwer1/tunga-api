# -*- coding: utf-8 -*-

from django.contrib import admin

from tunga_tasks.models import Task, Application, Participation, TimeEntry, ProgressEvent, ProgressReport, \
    Project, TaskPayment, ParticipantPayment, TaskInvoice, TaskAccess, Estimate, Quote, WorkActivity, \
    MultiTaskPaymentKey
from tunga_utils.admin import ReadOnlyModelAdmin


@admin.register(MultiTaskPaymentKey)
class MultiTaskPaymentKeyAdmin(admin.ModelAdmin):
    pass
    #list_display = ('title', 'amount', 'closed', 'created_at', 'archived')
    #list_filter = ('archived',)
    #search_fields = ('title',)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'deadline', 'closed', 'created_at', 'archived')
    list_filter = ('archived',)
    search_fields = ('title',)


class TaskAccessInline(admin.StackedInline):
    model = TaskAccess
    exclude = ('created_by',)
    extra = 1

    def save_model(self, request, obj, form, change):
        obj.created_by = request.user
        obj.save()


class ParticipationInline(admin.StackedInline):
    model = Participation
    exclude = ('created_by',)
    extra = 1

    def save_model(self, request, obj, form, change):
        obj.created_by = request.user
        obj.save()


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        'summary', 'user', 'type', 'scope', 'source', 'apply', 'closed', 'paid', 'archived', 'skills_list', 'created_at',
        'fee', 'bid', 'dev_rate', 'pm_rate', 'pm_time_percentage', 'tunga_percentage_dev', 'tunga_percentage_pm',
        'schedule_call_start'
    )
    list_filter = (
        'type', 'scope', 'source', 'apply', 'closed', 'paid', 'pay_distributed', 'archived',
        'created_at', 'schedule_call_start', 'paid_at'
    )
    search_fields = ('title', 'analytics_id')
    inlines = (TaskAccessInline, ParticipationInline)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            instance.created_by = request.user
            instance.save()
        formset.save_m2m()


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('task', 'user', 'status', 'created_at')
    list_filter = ('status', 'created_at')


@admin.register(Participation)
class ParticipationAdmin(admin.ModelAdmin):
    list_display = ('task', 'user', 'status', 'share', 'created_at')
    list_filter = ('status', 'created_at')


@admin.register(Estimate)
class EstimateAdmin(admin.ModelAdmin):
    list_display = ('task', 'user', 'status', 'moderated_by', 'reviewed_by', 'created_at')


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = ('task', 'user', 'status', 'moderated_by', 'reviewed_by', 'created_at')


@admin.register(WorkActivity)
class WorkActivityAdmin(admin.ModelAdmin):
    list_display = ('title', 'hours', 'due_at', 'created_at')


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = ('task', 'user', 'hours', 'spent_at', 'created_at')


@admin.register(ProgressEvent)
class ProgressEventAdmin(admin.ModelAdmin):
    list_display = ('task', 'title', 'type', 'due_at')
    list_filter = ('type', 'due_at')


@admin.register(ProgressReport)
class ProgressReportAdmin(admin.ModelAdmin):
    list_display = ('event', 'user', 'status', 'percentage', 'created_at')
    list_filter = ('status', 'created_at')


@admin.register(TaskPayment)
class TaskPaymentAdmin(ReadOnlyModelAdmin):
    list_display = ('task', 'payment_type', 'ref', 'btc_address', 'btc_received', 'btc_price', 'amount', 'currency', 'email', 'paid', 'captured', 'processed', 'created_at', 'received_at')
    list_filter = ('processed', 'created_at', 'received_at')
    search_fields = ('task__title',)


@admin.register(ParticipantPayment)
class ParticipantPaymentAdmin(ReadOnlyModelAdmin):
    list_display = (
        'participant', 'btc_sent', 'btc_received',
        'destination', 'ref', 'status', 'created_at', 'received_at'
    )
    list_filter = ('status', 'created_at', 'received_at')
    search_fields = (
        'participant__user__username', 'participant__user__first_name',
        'participant__user__last_name', 'participant__task__title'
    )


@admin.register(TaskInvoice)
class TaskInvoiceAdmin(ReadOnlyModelAdmin):
    list_display = ('number', 'task', 'display_fee', 'payment_method', 'created_at')
    list_filter = ('payment_method', 'created_at')
    search_fields = ('number', 'task__title')
