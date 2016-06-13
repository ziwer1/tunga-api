from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver

from tunga_utils.emails import send_contact_request_email
from tunga_utils.models import ContactRequest


@receiver(post_save, sender=ContactRequest)
def activity_handler_new_contact_request(sender, instance, created, **kwargs):
    if created:
        send_contact_request_email(instance)
