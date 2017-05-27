import stripe

from tunga.settings import STRIPE_SECRET


def get_client():
    stripe.api_key = STRIPE_SECRET
    client = stripe.http_client.RequestsClient()
    stripe.default_http_client = client
    return stripe
