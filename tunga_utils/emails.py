import datetime
import re

from django.core.mail.message import EmailMultiAlternatives
from django.template.exceptions import TemplateDoesNotExist
from django.template.loader import render_to_string
from django_rq.decorators import job
from premailer import premailer

from tunga.settings import DEFAULT_FROM_EMAIL, TUNGA_CONTACT_REQUEST_EMAIL_RECIPIENTS, EMAIL_SUBJECT_PREFIX
from tunga_utils.helpers import clean_instance, convert_to_text
from tunga_utils.models import ContactRequest
from tunga_utils.hubspot_utils import create_hubspot_engagement


def render_mail(subject, template_prefix, to_emails, context, bcc=None, cc=None, **kwargs):
    from_email = DEFAULT_FROM_EMAIL
    if not re.match(r'^\[\s*Tunga', subject):
        subject = '{} {}'.format(EMAIL_SUBJECT_PREFIX, subject)

    bodies = {}
    for ext in ['html', 'txt']:
        try:
            template_name = '{0}.{1}'.format(template_prefix, ext)
            bodies[ext] = render_to_string(template_name,
                                           context).strip()
        except TemplateDoesNotExist:
            if ext == 'txt':
                if 'html' in bodies:
                    # Compose text body from html
                    bodies[ext] = convert_to_text(bodies['html'])
                else:
                    # We need at least one body
                    raise

    if bodies:
        msg = EmailMultiAlternatives(subject, bodies['txt'], from_email, to_emails, bcc=bcc, cc=cc)
        if 'html' in bodies:
            try:
                html_body = render_to_string(
                    'tunga/email/base.html', dict(email_content=bodies['html'])
                ).strip()
            except TemplateDoesNotExist:
                html_body = bodies['html']
            msg.attach_alternative(premailer.transform(html_body), 'text/html')
    else:
        raise TemplateDoesNotExist
    return msg


def send_mail(subject, template_prefix, to_emails, context, bcc=None, cc=None, **kwargs):
    msg = render_mail(subject, template_prefix, to_emails, context, bcc=bcc, cc=cc, **kwargs)
    is_sent = msg.send()
    if is_sent:
        # Log engagement in HubSpot
        new_kwargs = kwargs
        new_kwargs.update(
            dict(cc=cc, bcc=bcc, context=context, template_prefix=template_prefix)
        )
        try:
            create_hubspot_engagement(
                from_email=msg.from_email, to_emails=msg.to, subject=msg.subject, body=msg.body, **kwargs
            )
        except:
            pass
    return is_sent


@job
def send_contact_request_email(instance):
    instance = clean_instance(instance, ContactRequest)

    subject = "New {} Request".format(instance.item and 'Offer' or 'Contact')
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
    if send_mail(subject, 'tunga/email/contact_request_message', to, ctx):
        instance.email_sent_at = datetime.datetime.utcnow()
        instance.save()
