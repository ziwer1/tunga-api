from actstream.signals import action
from django.contrib.admin.options import get_content_type_for_model
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver

from tunga_activity import verbs
from tunga_messages.models import Channel
from tunga_tasks.models import Task
from tunga_utils.emails import send_contact_request_email
from tunga_utils.models import ContactRequest, Upload


@receiver(post_save, sender=ContactRequest)
def activity_handler_new_contact_request(sender, instance, created, **kwargs):
    if created:
        send_contact_request_email.delay(instance.id)


@receiver(post_save, sender=Upload)
def activity_handler_new_upload(sender, instance, created, **kwargs):
    t = get_content_type_for_model(Task)
    if created and instance.content_type in [get_content_type_for_model(Channel), get_content_type_for_model(Task)]:
        action.send(instance.user, verb=verbs.UPLOAD, action_object=instance, target=instance.content_object)
