import datetime

from dateutil.relativedelta import relativedelta
from django.db.models.aggregates import Min, Max
from django_rq.decorators import job

from tunga_tasks.models import ProgressEvent, PROGRESS_EVENT_TYPE_SUBMIT, PROGRESS_EVENT_TYPE_PERIODIC, \
    UPDATE_SCHEDULE_ANNUALLY, UPDATE_SCHEDULE_HOURLY, UPDATE_SCHEDULE_DAILY, UPDATE_SCHEDULE_WEEKLY, \
    UPDATE_SCHEDULE_MONTHLY, UPDATE_SCHEDULE_QUATERLY, Task
from tunga_utils.decorators import convert_first_arg_to_instance, clean_instance


@job
def initialize_task_progress_events(task):
    task = clean_instance(task, Task)
    update_task_submit_milestone(task)
    update_task_periodic_updates(task)


@job
def update_task_submit_milestone(task):
    task = clean_instance(task, Task)
    if task.deadline:
        days_before = task.fee > 150 and 2 or 1
        submission_date = task.deadline - datetime.timedelta(days=days_before)
        defaults = {'due_at': submission_date, 'title': 'Submit final draft'}
        ProgressEvent.objects.update_or_create(task=task, type=PROGRESS_EVENT_TYPE_SUBMIT, defaults=defaults)


@job
def update_task_periodic_updates(task):
    task = clean_instance(task, Task)
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
                last_update_at = periodic_start_date
                while True:
                    next_update_at = last_update_at + relativedelta(**delta)
                    if not task.deadline or next_update_at < task.deadline:
                        ProgressEvent.objects.update_or_create(
                            task=task, type=PROGRESS_EVENT_TYPE_PERIODIC, due_at=next_update_at
                        )
                    if next_update_at > now:
                        break
                    else:
                        last_update_at = next_update_at
