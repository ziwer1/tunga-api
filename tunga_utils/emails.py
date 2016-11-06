import datetime

from django.core.mail.message import EmailMultiAlternatives, EmailMessage
from django.template.exceptions import TemplateDoesNotExist
from django.template.loader import render_to_string
from django_rq.decorators import job
from premailer import premailer

from tunga.settings import DEFAULT_FROM_EMAIL, TUNGA_CONTACT_REQUEST_EMAIL_RECIPIENTS, EMAIL_SUBJECT_PREFIX
from tunga_utils.helpers import clean_instance
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
            msg.attach_alternative(premailer.transform(bodies['html']), 'text/html')
    else:
        msg = EmailMessage(subject, premailer.transform(bodies['html']), from_email, to_emails, bcc=bcc, cc=cc)
        msg.content_subtype = 'html'  # Main content is now text/html
    return msg


def send_mail(subject, template_prefix, to_emails, context, bcc=None, cc=None, **kwargs):
    msg = render_mail(subject, template_prefix, to_emails, context, bcc=bcc, cc=cc, **kwargs)
    return msg.send()


@job
def send_contact_request_email(instance):
    instance = clean_instance(instance, ContactRequest)

    subject = "%s New %s Request" % (EMAIL_SUBJECT_PREFIX, instance.item and 'Offer' or 'Contact')
    msg_suffix = 'wants to know more about Tunga.'
    if instance.item:
        item_name = instance.get_item_display()
        subject = '%s (%s)' % (subject, item_name)
        msg_suffix = 'requested for "%s"' % item_name
    to = TUNGA_CONTACT_REQUEST_EMAIL_RECIPIENTS

    ctx = {
        'email': instance.email,
        'message': '%s %s ' % (
            instance.email,
            msg_suffix
        )
    }
    if send_mail(subject, 'tunga/email/email_contact_request_message', to, ctx):
        instance.email_sent_at = datetime.datetime.utcnow()
        instance.save()
