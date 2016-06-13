from tunga.settings import EMAIL_SUBJECT_PREFIX, TUNGA_URL, TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS
from tunga_utils.decorators import catch_all_exceptions
from tunga_utils.emails import send_mail


@catch_all_exceptions
def send_new_user_email(instance):
    subject = "%s %s joined Tunga" % (EMAIL_SUBJECT_PREFIX, instance.display_name)
    to = TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS
    ctx = {
        'user': instance,
        'user_url': '%s/member/%s/' % (TUNGA_URL, instance.id)
    }
    send_mail(subject, 'tunga/email/email_new_user', to, ctx)
