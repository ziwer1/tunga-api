import datetime

from django_rq.decorators import job

from tunga.settings import EMAIL_SUBJECT_PREFIX, TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS, TUNGA_URL
from tunga_profiles.models import DeveloperApplication
from tunga_utils.decorators import convert_first_arg_to_instance, clean_instance
from tunga_utils.emails import send_mail


@job
def send_new_developer_email(instance):
    instance = clean_instance(instance, DeveloperApplication)
    subject = "%s %s has applied to become a Tunga developer" % (EMAIL_SUBJECT_PREFIX, instance.display_name)
    to = TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS
    ctx = {
        'application': instance,
    }
    send_mail(subject, 'tunga/email/email_new_developer_application', to, ctx)


@job
def send_developer_application_received_email(instance):
    instance = clean_instance(instance, DeveloperApplication)
    subject = "%s Your application to become a Tunga developer has been received" % EMAIL_SUBJECT_PREFIX
    to = [instance.email]
    ctx = {
        'application': instance
    }
    send_mail(subject, 'tunga/email/email_developer_application_received', to, ctx)


@job
def send_developer_accepted_email(instance):
    instance = clean_instance(instance, DeveloperApplication)
    subject = "%s Your application to become a Tunga developer has been accepted" % EMAIL_SUBJECT_PREFIX
    to = [instance.email]
    ctx = {
        'application': instance,
        'invite_url': '%s/signup/developer/%s/' % (TUNGA_URL, instance.confirmation_key)
    }
    if send_mail(subject, 'tunga/email/email_developer_application_accepted', to, ctx):
        instance.confirmation_sent_at = datetime.datetime.utcnow()
        instance.save()
