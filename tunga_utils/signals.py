from django.core.mail.message import EmailMessage
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver
from django.template.loader import render_to_string

from tunga.settings import CONTACT_REQUEST_EMAIL_RECIPIENT, DEFAULT_FROM_EMAIL, EMAIL_SUBJECT_PREFIX
from tunga_utils.models import ContactRequest


@receiver(post_save, sender=ContactRequest)
def activity_handler_new_contact_request(sender, instance, created, **kwargs):
    if created:
        subject = "%s New Contact Request" % EMAIL_SUBJECT_PREFIX
        to = [CONTACT_REQUEST_EMAIL_RECIPIENT]
        from_email = DEFAULT_FROM_EMAIL

        message = render_to_string('tunga/email/email_contact_request_message.txt', {'email': instance.email})
        EmailMessage(subject, message, to=to, from_email=from_email).send()


