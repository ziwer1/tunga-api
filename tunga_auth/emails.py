from django.core.mail import EmailMessage
from django.template.loader import render_to_string

from tunga.settings import EMAIL_SUBJECT_PREFIX, TUNGA_URL, TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS
from tunga_utils.decorators import catch_all_exceptions


@catch_all_exceptions
def send_new_user_email(instance):
    subject = "%s %s joined Tunga" % (EMAIL_SUBJECT_PREFIX, instance.display_name)
    to = TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS

    message = render_to_string(
        'tunga/email/email_new_user.txt',
        {
            'user': instance,
            'user_url': '%s/member/%s/' % (TUNGA_URL, instance.id)
        }
    )
    EmailMessage(subject, message, to=to).send()
