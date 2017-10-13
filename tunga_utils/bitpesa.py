import hashlib
import hmac
import json
from decimal import Decimal
from uuid import uuid4

import requests

from tunga.settings import BITPESA_API_URL, BITPESA_API_SECRET, BITPESA_API_KEY
from tunga_utils.constants import CURRENCY_BTC, COUNTRY_CODE_TANZANIA, COUNTRY_CODE_UGANDA, COUNTRY_CODE_NIGERIA

PAY_METHOD_UGX_MOBILE = 'UGX::Mobile'
PAY_METHOD_TZS_MOBILE = 'TZS::Mobile'
PAY_METHOD_NGN_MOBILE = 'NGN::Mobile'

KEY_TRANSACTION = "transaction"
KEY_ID = "id"
KEY_REQUESTED_AMOUNT = "requested_amount"
KEY_INPUT_AMOUNT = "input_amount"
KEY_DUE_AMOUNT = "due_amount"
KEY_PAID_AMOUNT = "paid_amount"
KEY_INPUT_CURRENCY = "input_currency"
KEY_OUTPUT_CURRENCY = "output_currency"
KEY_REQUESTED_CURRENCY = "requested_currency"
KEY_RECIPIENTS = "recipients"
KEY_PAYIN_METHODS = "payin_methods"
KEY_PAYOUT_METHOD = "payout_method"
KEY_TYPE = "type"
KEY_DETAILS = "details"
KEY_IN_DETAILS = "in_details"
KEY_OUT_DETAILS = "out_details"
KEY_NAME = "name"
KEY_FIRST_NAME = "first_name"
KEY_LAST_NAME = "last_name"
KEY_PHONE_NUMBER = "phone_number"
KEY_BANK_ACCOUNT = "bank_account"
KEY_ADDRESS = "address"
KEY_BITCOIN_ADDRESS = "bitcoin_address"
KEY_OBJECT = "object"
KEY_SENDER = "sender"
KEY_METADATA = "metadata"
KEY_STATE = "state"
KEY_FUNDED = "funded"
KEY_CREATED_AT = "created_at"
KEY_EVENT = "event"
KEY_URL = "url"
KEY_STYLE = "style"
KEY_PROVIDER = "provider"
KEY_WEBHOOK = "webhook"

KEY_REFERENCE = "reference"
KEY_IDEM_KEY = "idem_key"

VALUE_INITIAL = "initial"
VALUE_FUNDED = "funded"
VALUE_PAID = "paid"
VALUE_CANCELED = "canceled"
VALUE_APPROVED = "approved"

EVENT_SENDER_APPROVED = "sender.approved"
EVENT_TRANSACTION_REQUEST_CREATED = "transaction_request.created"
EVENT_TRANSACTION_REQUEST_ACCEPTED = "transaction_request.accepted"
EVENT_TRANSACTION_REQUEST_REJECTED = "transaction_request.rejected"
EVENT_TRANSACTION_APPROVED = "transaction.approved"
EVENT_TRANSACTION_PAID_IN = "transaction.paid_in"
EVENT_TRANSACTION_PAID_OUT = "transaction.paid_out"
EVENT_TRANSACTION_MISPAID = "transaction.mispaid"
EVENT_RECIPIENT_PAID_OUT = "recipient.paid_out"

HEADER_AUTH_SIGNATURE = 'HTTP_AUTHORIZATION_SIGNATURE'
HEADER_AUTH_NONCE = 'HTTP_AUTHORIZATION_NONCE'

FEE_PERCENTAGE_MAP = {
    COUNTRY_CODE_UGANDA: 3,
    COUNTRY_CODE_TANZANIA: 3,
    COUNTRY_CODE_NIGERIA: 4.25
}

PAY_OUT_METHOD_MAP = {
    COUNTRY_CODE_UGANDA: PAY_METHOD_UGX_MOBILE,
    COUNTRY_CODE_TANZANIA: PAY_METHOD_TZS_MOBILE,
    COUNTRY_CODE_NIGERIA: PAY_METHOD_NGN_MOBILE
}


def get_endpoint_url(endpoint):
    return '%s%s' % (BITPESA_API_URL, endpoint)


def get_pay_out_amount(amount, country_code):
    share = Decimal(FEE_PERCENTAGE_MAP.get(country_code, 0))*Decimal(0.01)
    return Decimal(1-share)*amount


def get_pay_out_method(country_code):
    return PAY_OUT_METHOD_MAP.get(country_code, None)


def generate_signature(url, method, data, nonce):
    parts = [nonce, method.upper(), url, hashlib.sha512(json.dumps(data or {})).hexdigest()]

    signature_string = '&'.join(parts)
    return hmac.new(BITPESA_API_SECRET, msg=signature_string, digestmod=hashlib.sha512).hexdigest()


def verify_signature(signature, url, method, data, nonce):
    return signature == generate_signature(url, method, data, nonce)


def call_api(endpoint, method, nonce, data=None):
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization-Key': BITPESA_API_KEY,
        'Authorization-Nonce': nonce,
        'Authorization-Signature': generate_signature(endpoint, method, data, nonce)
    }

    kwargs = {'json': data or {}}
    return requests.request(method=method.lower(), url=endpoint, headers=headers, **kwargs)


def get_response_object(response):
    if isinstance(response, dict):
        return response.get(KEY_OBJECT, None)
    return None


def create_transaction(sender, recipients, input_currency=CURRENCY_BTC, transaction_id=None, nonce=None):
    nonce = nonce or str(uuid4())
    api_endpoint = get_endpoint_url('transactions')

    request_data = {
        KEY_TRANSACTION: {
            KEY_INPUT_CURRENCY: input_currency,
            KEY_RECIPIENTS: recipients,
            KEY_SENDER: sender,
            KEY_METADATA: {
                KEY_REFERENCE: transaction_id,
                KEY_IDEM_KEY: nonce
            }
        }
    }

    r = call_api(api_endpoint, 'POST', nonce, data=request_data)

    if r.status_code == 201:
        return get_response_object(r.json())
    return None


def create_sender(sender):
    r = call_api(get_endpoint_url('senders'), 'POST', str(uuid4()), data={KEY_SENDER: sender})

    if r.status_code == 201:
        return get_response_object(r.json())
    return None


def get_transaction(transaction_id):
    r = call_api(get_endpoint_url('transactions/{}'.format(transaction_id)), 'GET', str(uuid4()))

    if r.status_code == 200:
        return get_response_object(r.json())
    return r
