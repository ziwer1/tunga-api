# -*- coding: utf-8 -*-

import datetime
import json
import re
from decimal import Decimal
from uuid import uuid4

from dateutil.relativedelta import relativedelta
from django.db.models.aggregates import Min, Max
from django.db.models.query_utils import Q
from django_rq.decorators import job

from tunga.settings import BITPESA_SENDER
from tunga_profiles.models import ClientNumber
from tunga_profiles.utils import get_app_integration
from tunga_tasks.models import ProgressEvent, Task, ParticipantPayment, \
    TaskInvoice, Integration, IntegrationMeta, Participation, MultiTaskPaymentKey, TaskPayment
from tunga_utils import bitcoin_utils, coinbase_utils, bitpesa, harvest_utils
from tunga_utils.constants import CURRENCY_BTC, PAYMENT_METHOD_BTC_WALLET, \
    PAYMENT_METHOD_BTC_ADDRESS, PAYMENT_METHOD_MOBILE_MONEY, UPDATE_SCHEDULE_HOURLY, UPDATE_SCHEDULE_DAILY, \
    UPDATE_SCHEDULE_WEEKLY, UPDATE_SCHEDULE_MONTHLY, UPDATE_SCHEDULE_QUATERLY, UPDATE_SCHEDULE_ANNUALLY, \
    PROGRESS_EVENT_TYPE_PERIODIC, PROGRESS_EVENT_TYPE_SUBMIT, STATUS_PENDING, STATUS_PROCESSING, \
    STATUS_INITIATED, APP_INTEGRATION_PROVIDER_HARVEST, PROGRESS_EVENT_TYPE_COMPLETE, STATUS_ACCEPTED, \
    PROGRESS_EVENT_TYPE_PM, PROGRESS_EVENT_TYPE_CLIENT, TASK_PAYMENT_METHOD_BITCOIN
from tunga_utils.helpers import clean_instance
from tunga_utils.hubspot_utils import create_or_update_hubspot_deal


@job
def initialize_task_progress_events(task):
    task = clean_instance(task, Task)
    update_task_submit_milestone(task)
    update_task_periodic_updates(task)
    update_task_pm_updates(task)
    update_task_client_surveys(task)


@job
def update_task_submit_milestone(task):
    task = clean_instance(task, Task)
    if task.deadline:
        task_period = (task.deadline - task.created_at).days
        if task.parent:
            # task is part of a bigger project
            draft_submission_date = task.deadline
        else:
            # standalone task needs a milestone before the deadline
            days_before = (task.pay > 150 and task_period >= 7) and 2 or 1
            draft_submission_date = task.deadline - datetime.timedelta(days=days_before)

        draft_defaults = {'due_at': draft_submission_date, 'title': 'Final draft'}
        ProgressEvent.objects.update_or_create(task=task, type=PROGRESS_EVENT_TYPE_SUBMIT, defaults=draft_defaults)

        submit_defaults = {'due_at': task.deadline, 'title': 'Submit work'}
        ProgressEvent.objects.update_or_create(task=task, type=PROGRESS_EVENT_TYPE_COMPLETE, defaults=submit_defaults)


def clean_update_datetime(periodic_start_date, target_task=None):
    return periodic_start_date.replace(
        hour=target_task and target_task.created_at.hour or 12, minute=0, second=0, microsecond=0
    )


@job
def update_task_periodic_updates(task):
    task = clean_instance(task, Task)

    target_task = task
    if task.parent:
        # for sub-tasks, create all periodic updates on the project
        target_task = task.parent

    if target_task.closed or not target_task.updates_participants:
        # Only create schedule events for projects which aren't
        return

    if target_task.update_interval and target_task.update_interval_units:
        periodic_start_date = ProgressEvent.objects.filter(
            Q(task=target_task) | Q(task__parent=target_task), type=PROGRESS_EVENT_TYPE_PERIODIC
        ).aggregate(latest_date=Max('due_at'))['latest_date']

        now = datetime.datetime.utcnow()
        if periodic_start_date and periodic_start_date > now:
            return

        if not periodic_start_date:
            periodic_start_date = Participation.objects.filter(
                Q(task=target_task) | Q(task__parent=target_task), status=STATUS_ACCEPTED
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
            period_info = period_map.get(target_task.update_interval_units, None)
            if period_info:
                unit = isinstance(period_info, dict) and period_info.keys()[0] or period_info
                multiplier = isinstance(period_info, dict) and period_info.values()[0] or 1
                delta = dict()
                delta[unit] = multiplier * target_task.update_interval
                last_update_at = clean_update_datetime(periodic_start_date, target_task)
                while True:
                    next_update_at = last_update_at + relativedelta(**delta)
                    if next_update_at.weekday() in [5, 6]:
                        # Don't schedule updates on weekends
                        next_update_at += relativedelta(days=7 - next_update_at.weekday())

                    if next_update_at >= now:
                        future_by_18_hours = now + relativedelta(hours=18)
                        if (not target_task.pause_updates_until or target_task.pause_updates_until < next_update_at) \
                                and next_update_at <= future_by_18_hours and (
                            not target_task.deadline or next_update_at < target_task.deadline):
                            num_updates_within_on_same_day = ProgressEvent.objects.filter(
                                task=target_task, type=PROGRESS_EVENT_TYPE_PERIODIC,
                                due_at__contains=next_update_at.date()
                            ).count()

                            if num_updates_within_on_same_day == 0:
                                # Schedule at most one periodic update for any day
                                ProgressEvent.objects.update_or_create(
                                    task=target_task, type=PROGRESS_EVENT_TYPE_PERIODIC, due_at=next_update_at
                                )
                        break
                    else:
                        last_update_at = next_update_at


@job
def update_task_pm_updates(task):
    task = clean_instance(task, Task)

    target_task = task
    if task.parent:
        # for sub-tasks, create all pm updates on the project
        target_task = task.parent

    if target_task.closed or target_task.is_task or not target_task.approved or not target_task.pm:
        # only request pm updates for project which are approved and not closed
        return

    if target_task.update_interval and target_task.update_interval_units:
        periodic_start_date = ProgressEvent.objects.filter(
            Q(task=target_task) | Q(task__parent=target_task), type=PROGRESS_EVENT_TYPE_PM
        ).aggregate(latest_date=Max('due_at'))['latest_date']

        now = datetime.datetime.utcnow()
        if periodic_start_date and periodic_start_date > now:
            return

        if not periodic_start_date:
            periodic_start_date = datetime.datetime.utcnow()

        if periodic_start_date:
            last_update_at = clean_update_datetime(periodic_start_date, target_task)
            while True:
                last_update_day = last_update_at.weekday()
                next_update_at = last_update_at
                if last_update_day < 3:
                    # Last was before Thursday so schedule for Thursday
                    next_update_at += relativedelta(days=3 - last_update_day)
                else:
                    # Last was on after Thursday so schedule for Monday
                    next_update_at += relativedelta(days=7 - last_update_day)

                if next_update_at >= now:
                    future_by_18_hours = now + relativedelta(hours=18)
                    if next_update_at <= future_by_18_hours and (
                        not target_task.deadline or next_update_at < target_task.deadline):
                        num_updates_within_on_same_day = ProgressEvent.objects.filter(
                            task=target_task, type=PROGRESS_EVENT_TYPE_PM,
                            due_at__contains=next_update_at.date()
                        ).count()

                        if num_updates_within_on_same_day == 0:
                            # Schedule at most one pm update for any day
                            ProgressEvent.objects.update_or_create(
                                task=target_task, type=PROGRESS_EVENT_TYPE_PM,
                                due_at=next_update_at, defaults={'title': 'PM Report'}
                            )
                    break
                else:
                    last_update_at = next_update_at


@job
def update_task_client_surveys(task):
    task = clean_instance(task, Task)

    target_task = task
    if task.parent:
        # for sub-tasks, create all surveys on the project
        target_task = task.parent

    if target_task.closed or not (
            target_task.survey_client and target_task.approved and target_task.active_participants):
        # only conduct survey for approved tasks that have been assigned devs and aren't closed
        return

    if target_task.update_interval and target_task.update_interval_units:
        periodic_start_date = ProgressEvent.objects.filter(
            Q(task=target_task) | Q(task__parent=target_task), type=PROGRESS_EVENT_TYPE_CLIENT
        ).aggregate(latest_date=Max('due_at'))['latest_date']

        now = datetime.datetime.utcnow()
        if periodic_start_date and periodic_start_date > now:
            return

        if not periodic_start_date:
            periodic_start_date = datetime.datetime.utcnow()

        if periodic_start_date:
            last_update_at = clean_update_datetime(periodic_start_date, target_task)
            while True:
                last_update_day = last_update_at.weekday()
                # Schedule next survey for Monday
                next_update_at = last_update_at + relativedelta(days=7 - last_update_day)

                if next_update_at >= now:
                    future_by_18_hours = now + relativedelta(hours=18)
                    if next_update_at <= future_by_18_hours and (
                        not target_task.deadline or next_update_at < target_task.deadline):
                        num_updates_on_same_day = ProgressEvent.objects.filter(
                            task=target_task, type=PROGRESS_EVENT_TYPE_CLIENT,
                            due_at__contains=next_update_at.date()
                        ).count()

                        if num_updates_on_same_day == 0:
                            # Schedule at most one survey for any day
                            ProgressEvent.objects.update_or_create(
                                task=target_task, type=PROGRESS_EVENT_TYPE_CLIENT,
                                due_at=next_update_at, defaults={'title': 'Weekly Survey'}
                            )
                    break
                else:
                    last_update_at = next_update_at


@job
def distribute_task_payment(task):
    task = clean_instance(task, Task)
    if not task.paid:
        return

    if task.pay_distributed:
        return

    pay_description = task.summary

    participation_shares = task.get_payment_shares()
    # Distribute all payments for this task
    payments = TaskPayment.objects.filter(
        Q(multi_pay_key__tasks=task) | Q(multi_pay_key__distribute_tasks=task) | (Q(task=task) & Q(processed=False)),
        received_at__isnull=False, payment_type=TASK_PAYMENT_METHOD_BITCOIN
    )
    task_distribution = []
    for payment in payments:
        portion_distribution = []
        for item in participation_shares:
            participant = item['participant']
            share = item['share']
            portion_sent = False

            if not participant.user:
                continue

            participant_pay, created = ParticipantPayment.objects.get_or_create(
                source=payment, participant=participant
            )
            payment_method = participant.user.payment_method
            if created or (participant_pay and participant_pay.status == STATUS_PENDING):
                if payment_method in [PAYMENT_METHOD_BTC_ADDRESS, PAYMENT_METHOD_BTC_WALLET]:
                    if not (participant_pay.destination and bitcoin_utils.is_valid_btc_address(
                            participant_pay.destination)):
                        participant_pay.destination = participant.user.btc_address
                    transaction = send_payment_share(
                        destination=participant_pay.destination,
                        amount=Decimal(share) * payment.task_btc_share(task),
                        idem=str(participant_pay.idem_key),
                        description='%s - %s' % (pay_description, participant.user.display_name)
                    )
                    if transaction.status not in [
                        coinbase_utils.TRANSACTION_STATUS_FAILED, coinbase_utils.TRANSACTION_STATUS_EXPIRED,
                        coinbase_utils.TRANSACTION_STATUS_CANCELED
                    ]:
                        participant_pay.ref = transaction.id
                        participant_pay.btc_sent = abs(Decimal(transaction.amount.amount))
                        participant_pay.status = STATUS_PROCESSING
                        participant_pay.save()
                        portion_sent = True
                elif payment_method == PAYMENT_METHOD_MOBILE_MONEY:
                    share_amount = Decimal(share) * payment.task_btc_share(task)
                    recipients = [
                        {
                            bitpesa.KEY_REQUESTED_AMOUNT: float(
                                bitcoin_utils.get_valid_btc_amount(share_amount)
                            ),
                            bitpesa.KEY_REQUESTED_CURRENCY: CURRENCY_BTC,
                            bitpesa.KEY_PAYOUT_METHOD: {
                                bitpesa.KEY_TYPE: bitpesa.get_pay_out_method(participant.user.mobile_money_cc),
                                bitpesa.KEY_DETAILS: {
                                    bitpesa.KEY_FIRST_NAME: participant.user.first_name,
                                    bitpesa.KEY_LAST_NAME: participant.user.last_name,
                                    bitpesa.KEY_PHONE_NUMBER: participant.user.mobile_money_number
                                }
                            }
                        }
                    ]
                    bitpesa_nonce = str(uuid4())
                    transaction = bitpesa.create_transaction(
                        BITPESA_SENDER, recipients, input_currency=CURRENCY_BTC,
                        transaction_id=participant_pay.id, nonce=bitpesa_nonce
                    )
                    if transaction:
                        participant_pay.ref = transaction.get(bitpesa.KEY_ID, None)
                        participant_pay.status = STATUS_INITIATED
                        participant_pay.extra = bitpesa_nonce
                        participant_pay.save()

                        if complete_bitpesa_payment(transaction):
                            portion_sent = True
            elif participant_pay and payment_method == PAYMENT_METHOD_MOBILE_MONEY and \
                            participant_pay.status == STATUS_INITIATED:
                transaction_details = bitpesa.call_api(
                    bitpesa.get_endpoint_url('transactions/%s' % participant_pay.ref),
                    'GET', str(uuid4()), data={}
                )
                transaction = transaction_details.json().get(bitpesa.KEY_OBJECT)
                if transaction and complete_bitpesa_payment(transaction):
                    portion_sent = True

            portion_distribution.append(portion_sent)
        if portion_distribution and False not in portion_distribution:
            payment.processed = True
            payment.save()
            task_distribution.append(True)
        else:
            task_distribution.append(False)
    if task_distribution and not (False in task_distribution):
        task.pay_distributed = True
        task.save()


def complete_bitpesa_payment(transaction):
    bp_transaction_id = transaction.get(bitpesa.KEY_ID, None)
    metadata = transaction.get(bitpesa.KEY_METADATA, None)
    reference = metadata.get(bitpesa.KEY_REFERENCE, None)
    bp_idem_key = metadata.get(bitpesa.KEY_IDEM_KEY, None)

    input_amount = Decimal('%s' % transaction.get(bitpesa.KEY_INPUT_AMOUNT, 0))
    payin_methods = transaction.get(bitpesa.KEY_PAYIN_METHODS, None)

    destination_address = None
    if payin_methods:
        out_details = payin_methods[0][bitpesa.KEY_OUT_DETAILS]
        # Key was originally 'bitcoin_address' on first test but it appeared to have 'Address',
        # Check both for redundancy and inquire from BitPesa on this
        if bitpesa.KEY_BITCOIN_ADDRESS in out_details:
            destination_address = out_details.get(bitpesa.KEY_BITCOIN_ADDRESS, None)
        else:
            destination_address = out_details.get("Address", None)
        if not destination_address:
            destination_address = payin_methods[0][bitpesa.KEY_IN_DETAILS].get(bitpesa.KEY_ADDRESS, None)

    if destination_address:
        try:
            payment = ParticipantPayment.objects.get(
                id=reference, ref=bp_transaction_id, extra=bp_idem_key, status=STATUS_INITIATED
            )
        except:
            payment = None

        if payment:
            transaction_state = transaction.get(bitpesa.KEY_STATE, None)
            if transaction_state == bitpesa.VALUE_APPROVED:
                share_amount = Decimal(
                    bitcoin_utils.get_valid_btc_amount(
                        payment.source.btc_received * Decimal(payment.participant.payment_share)
                    )
                )

                if input_amount <= share_amount:
                    cb_transaction = send_payment_share(
                        destination=destination_address,
                        amount=input_amount,
                        idem=str(payment.idem_key),
                        description='%s - %s' % (
                            payment.participant.task.summary, payment.participant.user.display_name
                        )
                    )
                    if cb_transaction.status not in [
                        coinbase_utils.TRANSACTION_STATUS_FAILED, coinbase_utils.TRANSACTION_STATUS_EXPIRED,
                        coinbase_utils.TRANSACTION_STATUS_CANCELED
                    ]:
                        payment.btc_sent = input_amount
                        payment.destination = destination_address
                        payment.ref = cb_transaction.id
                        payment.status = STATUS_PROCESSING
                        payment.extra = json.dumps(dict(bitpesa=bp_transaction_id))
                        payment.save()
                        return True
            elif transaction_state == bitpesa.VALUE_CANCELED:
                # Fail for canceled BitPesa transactions
                if payment.status == STATUS_INITIATED:
                    # Switch status to pending if BTC hasn't already been sent
                    payment.status = STATUS_PENDING
                    payment.save()
    return False


def send_payment_share(destination, amount, idem, description=None):
    client = coinbase_utils.get_api_client()
    account = client.get_primary_account()
    transaction = account.send_money(
        to=destination,
        amount=bitcoin_utils.get_valid_btc_amount(amount),
        currency=CURRENCY_BTC,
        idem=idem,
        description=description
    )
    return transaction


@job
def generate_invoice_number(invoice):
    invoice = clean_instance(invoice, TaskInvoice)
    if not invoice.number:
        client, created = ClientNumber.objects.get_or_create(user=invoice.client)
        client_number = client.number
        task_number = invoice.task.task_number
        previous_for_month = TaskInvoice.objects.filter(
            created_at__year=invoice.created_at.year,
            created_at__month=invoice.created_at.month,
            created_at__lt=invoice.created_at
        ).count()

        month_number = previous_for_month + 1
        invoice_number = '%s%s%s%s' % (
            client_number, invoice.created_at.strftime('%Y%m'), '{:02d}'.format(month_number), task_number
        )
        invoice.number = invoice_number
        invoice.save()
    return invoice


@job
def complete_harvest_integration(integration):
    integration = clean_instance(integration, Integration)
    if integration.provider != APP_INTEGRATION_PROVIDER_HARVEST:
        return

    user = integration.task.user
    app_integration = get_app_integration(user=integration.task.user, provider=APP_INTEGRATION_PROVIDER_HARVEST)
    if app_integration and app_integration.extra:
        token = json.loads(app_integration.extra)

        project_id = integration.project_id

        harvest_client = harvest_utils.get_api_client(token, user=user, return_response_obj=True)

        # Create the task and assign it to the project in Harvest
        resp_task_assignment = harvest_client.create_task_to_project(
            project_id, task=dict(
                name='Tunga: {}'.format(integration.task.title)
            )
        )

        # TODO: Harvest isn't returning the created object, find a work around
        if resp_task_assignment and resp_task_assignment.headers:
            task_assignment_path = resp_task_assignment.headers.get('Location', '')

            m = re.match(
                r'^/projects/(?P<project_id>\d+)/task_assignments/(?P<task_assignment_id>\d+)',
                task_assignment_path,
                flags=re.IGNORECASE
            )
            if m:
                matches = m.groupdict()
                if matches.get('project_id', None) == project_id:
                    task_assignment_id = matches.get('task_assignment_id', None)

                    if task_assignment_id:
                        resp_task_assignment_retrieve = harvest_client.get_one_task_assigment(project_id,
                                                                                              task_assignment_id)
                        task_assignment = resp_task_assignment_retrieve.json()

                        defaults = {
                            'created_by': user,
                            'meta_key': 'project_task_id',
                            'meta_value': task_assignment['task_assignment']['task_id']
                        }

                        try:
                            IntegrationMeta.objects.update_or_create(
                                integration=integration, meta_key=defaults['meta_key'], defaults=defaults
                            )
                        except:
                            pass

        # Create task participants in Harvest
        participants = integration.task.participation_set.filter(status=STATUS_ACCEPTED)
        for participant in participants:
            harvest_client.create_user(
                user={
                    'email': participant.user.email,
                    'first-name': participant.user.first_name,
                    'last-name': participant.user.last_name
                }
            )


@job
def create_or_update_hubspot_deal_task(task, **kwargs):
    print('Create deal', kwargs)
    task = clean_instance(task, Task)
    create_or_update_hubspot_deal(task, **kwargs)


@job
def distribute_multi_task_payment(multi_task_key):
    multi_task_key = clean_instance(multi_task_key, MultiTaskPaymentKey)
    if not multi_task_key.paid:
        return

    # Distribute connected tasks
    for task in multi_task_key.tasks.all():
        distribute_task_payment(task)


@job
def update_multi_tasks(multi_task_key, distribute=False):
    multi_task_key = clean_instance(multi_task_key, MultiTaskPaymentKey)

    if multi_task_key.distribute_only:
        connected_tasks = multi_task_key.distribute_tasks
        connected_tasks.filter(paid=True).update(
            btc_price=multi_task_key.btc_price,
            withhold_tunga_fee_distribute=multi_task_key.withhold_tunga_fee,
            btc_paid=multi_task_key.paid,
            btc_paid_at=multi_task_key.paid_at
        )
    else:
        connected_tasks = multi_task_key.tasks
        connected_tasks.filter(paid=False).update(
            payment_method=multi_task_key.payment_method,
            btc_price=multi_task_key.btc_price,
            withhold_tunga_fee=multi_task_key.withhold_tunga_fee,
            paid=multi_task_key.paid,
            paid_at=multi_task_key.paid_at,
            processing=multi_task_key.processing,
            processing_at=multi_task_key.processing_at
        )

    # Generate invoices for all connected tasks
    for task in connected_tasks.all():
        if multi_task_key.distribute_only:
            if task.paid and multi_task_key.paid:
                distribute_task_payment.delay(task.id)
            return

        # Save Invoice
        if not task.btc_address or not bitcoin_utils.is_valid_btc_address(task.btc_address):
            address = coinbase_utils.get_new_address(coinbase_utils.get_api_client())
            task.btc_address = address
            task.save()

        TaskInvoice.objects.create(
            task=task,
            user=multi_task_key.user,
            title=task.title,
            fee=task.pay,
            client=task.owner or task.user,
            # developer=developer,
            payment_method=multi_task_key.payment_method,
            btc_price=multi_task_key.btc_price,
            btc_address=task.btc_address,
            withhold_tunga_fee=multi_task_key.withhold_tunga_fee
        )

        if distribute and multi_task_key.paid:
            distribute_task_payment.delay(task.id)
