import datetime
from dateutil.relativedelta import relativedelta
from django.db.models.aggregates import Min, Max

from tunga_tasks.models import ProgressEvent, PROGRESS_EVENT_TYPE_SUBMIT, PROGRESS_EVENT_TYPE_PERIODIC, \
    UPDATE_SCHEDULE_ANNUALLY, UPDATE_SCHEDULE_HOURLY, UPDATE_SCHEDULE_DAILY, UPDATE_SCHEDULE_WEEKLY, \
    UPDATE_SCHEDULE_MONTHLY, UPDATE_SCHEDULE_QUATERLY
from tunga_utils.decorators import catch_all_exceptions


@catch_all_exceptions
def initialize_task_progress_events(task):
    update_task_submit_milestone(task)
    update_task_periodic_updates(task)


@catch_all_exceptions
def update_task_submit_milestone(task):
    if task.deadline:
        days_before = task.fee > 150 and 2 or 1
        submission_date = task.deadline - datetime.timedelta(days=days_before)
        defaults = {'due_at': submission_date, 'title': 'Submit final draft'}
        ProgressEvent.objects.update_or_create(task=task, type=PROGRESS_EVENT_TYPE_SUBMIT, defaults=defaults)


@catch_all_exceptions
def update_task_periodic_updates(task):
    if task.update_interval and task.update_interval_units:
        periodic_start_date = task.progressevent_set.filter(
            task=task, type=PROGRESS_EVENT_TYPE_PERIODIC
        ).aggregate(latest_date=Max('due_at'))['latest_date']

        now = datetime.datetime.utcnow()
        if periodic_start_date and periodic_start_date > now:
            return

        if not periodic_start_date:
            periodic_start_date = task.participation_set.filter(
                task=task, accepted=True
            ).aggregate(start_date=Min('activated_at'))['start_date']

        if periodic_start_date:
            period_map = {
                UPDATE_SCHEDULE_HOURLY: 'hours',
                UPDATE_SCHEDULE_DAILY: 'days',
                UPDATE_SCHEDULE_WEEKLY: 'weeks',
                UPDATE_SCHEDULE_MONTHLY: 'months',
                UPDATE_SCHEDULE_QUATERLY: {'months': 3},
                UPDATE_SCHEDULE_ANNUALLY: 'years'
            }
            period_info = period_map.get(task.update_interval_units, None)
            if period_info:
                unit = isinstance(period_info, dict) and period_info.keys()[0] or period_info
                multiplier = isinstance(period_info, dict) and period_info.values()[0] or 1
                delta = {unit: multiplier*task.update_interval_units}
                while True:
                    next_update = periodic_start_date + relativedelta(**delta)
                    if not task.deadline or next_update < task.deadline:
                        next_update_info = {'due_at': next_update, 'type': PROGRESS_EVENT_TYPE_PERIODIC}
                        ProgressEvent.objects.update_or_create(task=task, defaults=next_update_info)
                    if next_update > now:
                        break
