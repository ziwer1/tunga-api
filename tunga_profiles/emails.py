import uuid

import datetime

from tunga.settings import EMAIL_SUBJECT_PREFIX, TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS
from tunga.settings.base import TUNGA_URL
from tunga_utils.decorators import catch_all_exceptions
from tunga_utils.emails import send_mail


@catch_all_exceptions
def send_new_developer_email(instance):
    subject = "%s %s has applied to become a Tunga developer" % (EMAIL_SUBJECT_PREFIX, instance.display_name)
    to = TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS
    ctx = {
        'application': instance,
    }
    send_mail(subject, 'tunga/email/email_new_developer_application', to, ctx)


#@catch_all_exceptions
def send_developer_accepted_email(instance):
    subject = "%s Your application to become a Tunga developer has been accepted" % EMAIL_SUBJECT_PREFIX
    to = [instance.email]
    ctx = {
        'application': instance,
        'invite_url': '%s/signup/developer/%s/' % (TUNGA_URL, instance.confirmation_key)
    }
    if send_mail(subject, 'tunga/email/email_developer_application_accepted', to, ctx):
        instance.confirmation_sent_at = datetime.datetime.utcnow()
