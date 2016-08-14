import datetime

from django.core.mail.message import EmailMultiAlternatives, EmailMessage
from django.template.exceptions import TemplateDoesNotExist
from django.template.loader import render_to_string
from django_rq.decorators import job

from tunga.settings import DEFAULT_FROM_EMAIL, CONTACT_REQUEST_EMAIL_RECIPIENT, EMAIL_SUBJECT_PREFIX
from tunga_utils.decorators import clean_instance
from tunga_utils.models import ContactRequest


def render_mail(subject, template_prefix, to_emails, context, bcc=None, cc=None, **kwargs):
    from_email = DEFAULT_FROM_EMAIL

    bodies = {}
    for ext in ['html', 'txt']:
        try:
            template_name = '{0}.{1}'.format(template_prefix, ext)
            bodies[ext] = render_to_string(template_name,
                                           context).strip()
        except TemplateDoesNotExist:
            if ext == 'txt' and not bodies:
                # We need at least one body
                raise
    if 'txt' in bodies:
        msg = EmailMultiAlternatives(subject, bodies['txt'], from_email, to_emails, bcc=bcc, cc=cc)
        if 'html' in bodies:
            msg.attach_alternative(bodies['html'], 'text/html')
    else:
        msg = EmailMessage(subject, bodies['html'], from_email, to_emails, bcc=bcc, cc=cc)
        msg.content_subtype = 'html'  # Main content is now text/html
    return msg


def send_mail(subject, template_prefix, to_emails, context, bcc=None, cc=None, **kwargs):
    msg = render_mail(subject, template_prefix, to_emails, context, bcc=bcc, cc=cc, **kwargs)
    return msg.send()


@job
def send_contact_request_email(instance):
    instance = clean_instance(instance, ContactRequest)
    subject = "%s New Contact Request" % EMAIL_SUBJECT_PREFIX
    to = [CONTACT_REQUEST_EMAIL_RECIPIENT]
    ctx = {'email': instance.email}
    if send_mail(subject, 'tunga/email/email_contact_request_message', to, ctx):
        instance.email_sent_at = datetime.datetime.utcnow()
        instance.save()
