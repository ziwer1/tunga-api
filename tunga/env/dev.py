DEBUG = True

AUTH_PASSWORD_VALIDATORS = []

EMAIL_SUBJECT_PREFIX = '[Tunga Test] '

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

ACCOUNT_EMAIL_VERIFICATION = 'optional'

CORS_ORIGIN_WHITELIST = ('localhost:8080', '127.0.0.1:8080', 'tunga.dev:8080', 'lightbox.tunga.io')

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_HEADERS = (
    'x-requested-with',
    'content-type',
    'accept',
    'origin',
    'authorization',
    'x-csrftoken',
    'X-CSRFToken',
    'X-EDIT-TOKEN'
)

TUNGA_URL = 'http://test.tunga.io'

"""
COINBASE_BASE_URL = 'https://sandbox.coinbase.com'

COINBASE_BASE_API_URL = 'https://api.sandbox.coinbase.com'

BITONIC_URL = 'https://niels-bitonic-664-web.garage.bitonic.nl:33488'
"""

HUBSPOT_API_KEY = 'aabefdb6-ffc8-4bed-bfbe-33858f4ff3b9'

try:
    from .local import *
except ImportError:
    pass
