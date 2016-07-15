from coinbase.wallet.client import Client, OAuthClient

from tunga.settings import COINBASE_BASE_URL, COINBASE_CLIENT_ID, COINBASE_SCOPES, \
    COINBASE_BASE_API_URL, COINBASE_API_KEY, COINBASE_API_SECRET


PAYLOAD_ID = 'id'

PAYLOAD_TYPE = 'type'
PAYLOAD_TYPE_NEW_PAYMENT = 'wallet:addresses:new-payment'

PAYLOAD_DATA = 'data'
PAYLOAD_ADDRESS = 'address'
PAYLOAD_CREATED_AT = 'created_at'

PAYLOAD_ADDITIONAL_DATA = 'additional_data'
PAYLOAD_AMOUNT = 'amount'

HEADER_COINBASE_SIGNATURE = 'HTTP_CB_SIGNATURE'

TRANSACTION_STATUS_PENDING = "pending"
TRANSACTION_STATUS_COMPLETED = "completed"
TRANSACTION_STATUS_FAILED = "failed"
TRANSACTION_STATUS_EXPIRED = "expired"
TRANSACTION_STATUS_CANCELED = "canceled"
TRANSACTION_STATUS_WAITING_FOR_SIGNATURE = "waiting_for_signature"
TRANSACTION_STATUS_WAITING_FOR_CLEARING = "waiting_for_clearing"


def get_authorize_url(redirect_uri):
    return '%s/oauth/authorize?client_id=%s&response_type=code&scope=%s&redirect_uri=%s' % (
        COINBASE_BASE_URL, COINBASE_CLIENT_ID, ','.join(COINBASE_SCOPES), redirect_uri
    )


def get_token_url():
    return '%s/oauth/token' % COINBASE_BASE_URL


def get_api_client():
    return Client(COINBASE_API_KEY, COINBASE_API_SECRET, base_api_uri=COINBASE_BASE_API_URL)


def get_oauth_client(access_token, refresh_token):
    return OAuthClient(access_token, refresh_token, base_api_uri=COINBASE_BASE_API_URL)


def get_new_address(client):
    account = client.get_primary_account()
    address = account.create_address()
    return address.address


def get_btc_price(currency):
    client = get_api_client()
    price = client.get_spot_price(**{'currency': currency})
    return price.amount
