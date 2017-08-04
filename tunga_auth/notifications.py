from django.contrib.auth import get_user_model
from django_rq.decorators import job

from tunga.settings import TUNGA_URL, TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS
from tunga_utils.emails import send_mail
from tunga_utils.helpers import clean_instance


@job
def send_new_user_email(instance):
    instance = clean_instance(instance, get_user_model())
    subject = "{} joined Tunga".format(instance.display_name)
    to = TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS
    ctx = {
        'user': instance,
        'user_url': '%s/people/%s/' % (TUNGA_URL, instance.username)
    }
    send_mail(subject, 'tunga/email/new_user', to, ctx)
