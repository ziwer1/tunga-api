import hashlib
import hmac
import json

import requests

from tunga.settings import BITPESA_API_URL, BITPESA_API_SECRET, BITPESA_API_KEY


def get_endpoint_url(endpoint):
    return '%s%s' % (BITPESA_API_URL, endpoint)


def make_bitpesa_api_call(endpoint, method, nonce, data=None):
    parts = [nonce, method.upper(), endpoint]
    if data:
        parts.append(hashlib.sha512(json.dumps(data)).hexdigest())

    signature_string = '&'.join(parts)
    print signature_string

    signature = hmac.new(BITPESA_API_SECRET, msg=signature_string, digestmod=hashlib.sha512).hexdigest()
    print signature

    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization-Key': BITPESA_API_KEY,
        'Authorization-Nonce': nonce,
        'Authorization-Signature': signature
    }

    kwargs = {}
    if data:
        kwargs['json'] = data

    return requests.request(method=method.lower(), url=endpoint, headers=headers, **kwargs)
