import datetime

from dateutil.relativedelta import relativedelta
from decimal import Decimal
from django.db.models.aggregates import Min, Max
from django_rq.decorators import job

from tunga_profiles.models import UserProfile, PAYMENT_METHOD_BTC_ADDRESS, PAYMENT_METHOD_BTC_WALLET, \
    BTC_WALLET_PROVIDER_COINBASE
from tunga_tasks.models import ProgressEvent, PROGRESS_EVENT_TYPE_SUBMIT, PROGRESS_EVENT_TYPE_PERIODIC, \
    UPDATE_SCHEDULE_ANNUALLY, UPDATE_SCHEDULE_HOURLY, UPDATE_SCHEDULE_DAILY, UPDATE_SCHEDULE_WEEKLY, \
    UPDATE_SCHEDULE_MONTHLY, UPDATE_SCHEDULE_QUATERLY, Task, Participation, ParticipantPayment, \
    PAYMENT_STATUS_PROCESSING
from tunga_utils import bitcoin_utils, coinbase_utils
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


@job
def distribute_task_payment(task):
    task = clean_instance(task, Task)
    if not task.paid:
        return

    if task.pay_distributed:
        return

    pay_description = task.summary.encode('utf-8')

    participation_shares = task.get_payment_shares()
    payments = task.taskpayment_set.filter(received_at__isnull=False, processed=False)
    for payment in payments:
        for item in participation_shares:
            participant = item['participant']
            share = item['share']
            destination_address = get_btc_payment_destination_address(participant.user)
            if not destination_address:
                continue

            participant_pay, created = ParticipantPayment.objects.get_or_create(
                source=payment, participant=participant, defaults={'destination': destination_address}
            )
            if created:
                transaction = send_payment_share(
                    destination_address, get_share_amount(share, payment.btc_received), pay_description
                )
                if transaction.status not in [
                    coinbase_utils.TRANSACTION_STATUS_FAILED, coinbase_utils.TRANSACTION_STATUS_EXPIRED,
                    coinbase_utils.TRANSACTION_STATUS_CANCELED
                ]:
                    participant_pay.ref = transaction.id
                    participant_pay.btc_sent = abs(Decimal(transaction.amount.amount))
                    participant_pay.status = PAYMENT_STATUS_PROCESSING
                    participant_pay.save()


def get_btc_payment_destination_address(user):
    user_profile = None
    try:
        user_profile = user.userprofile
    except:
        pass

    if not user_profile:
        return None

    if user_profile.payment_method == PAYMENT_METHOD_BTC_ADDRESS:
        if bitcoin_utils.is_valid_btc_address(user_profile.btc_address):
            return user_profile.btc_address
    elif user_profile.payment_method == PAYMENT_METHOD_BTC_WALLET:
        wallet = user_profile.btc_wallet
        if wallet.provider == BTC_WALLET_PROVIDER_COINBASE:
            client = coinbase_utils.get_oauth_client(wallet.token, wallet.token_secret)
            return coinbase_utils.get_new_address(client)
    return None


def get_share_amount(share, total):
    return Decimal(share)*total


def get_btc_amount(amount):
    return '{0:.6f}'.format(amount)


def send_payment_share(destination, amount, description=None):
    client = coinbase_utils.get_api_client()
    account = client.get_primary_account()
    transaction = account.send_money(
        to=destination, amount=get_btc_amount(amount), currency="BTC", description=description
    )
    return transaction
