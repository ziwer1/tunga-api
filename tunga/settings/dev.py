from .base import *


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '!8g-9plb-5pa795jxv4@f18fu-+j^h2cyk_-?p%4s31eudmmr+'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

AUTH_PASSWORD_VALIDATORS = []

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
    'X-CSRFToken'
)


try:
    from .local import *
except ImportError:
    pass

if DEBUG:
    STATICFILES_DIRS = (
        os.path.join(BASE_DIR, 'static'),
    )
    STATIC_ROOT = None

    for template_engine in TEMPLATES:
        template_engine['OPTIONS']['debug'] = True
