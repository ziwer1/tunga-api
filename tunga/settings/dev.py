from .base import *


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '!8g-9plb-5pa795jxv4@f18fu-+j^h2cyk_-?p%4s31eudmmr+'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

if DEBUG:
    STATICFILES_DIRS = (
        os.path.join(BASE_DIR, 'static'),
    )
    STATIC_ROOT = None

for template_engine in TEMPLATES:
    template_engine['OPTIONS']['debug'] = True

AUTH_PASSWORD_VALIDATORS = []

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'


try:
    from .local import *
except ImportError:
    pass
