from actstream.signals import action
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver

from tunga_activity import verbs
from tunga_profiles.notifications import send_new_developer_email, send_developer_accepted_email, \
    send_developer_application_received_email, send_new_skill_email, send_developer_invited_email
from tunga_profiles.models import Connection, DeveloperApplication, Skill, DeveloperInvitation
from tunga_utils.constants import REQUEST_STATUS_ACCEPTED, STATUS_ACCEPTED, STATUS_REJECTED


@receiver(post_save, sender=Connection)
def activity_handler_new_connection(sender, instance, created, **kwargs):
    if created:
        action.send(
            instance.from_user, verb=verbs.CONNECT, action_object=instance, target=instance.to_user)
    else:
        update_fields = kwargs.get('update_fields', None)
        if update_fields:
            if 'status' in update_fields and instance.status == STATUS_ACCEPTED:
                action.send(instance.to_user, verb=verbs.ACCEPT, action_object=instance)
            elif 'status' in update_fields and not instance.status == STATUS_REJECTED:
                action.send(instance.to_user, verb=verbs.REJECT, action_object=instance)


@receiver(post_save, sender=DeveloperApplication)
def activity_handler_developer_application(sender, instance, created, **kwargs):
    if created:
        send_new_developer_email.delay(instance.id)

        send_developer_application_received_email.delay(instance.id)
    else:
        if instance.status == REQUEST_STATUS_ACCEPTED and not instance.confirmation_sent_at:
            send_developer_accepted_email.delay(instance.id)


@receiver(post_save, sender=Skill)
def activity_handler_new_skill(sender, instance, created, **kwargs):
    if created:
        send_new_skill_email.delay(instance.id)


@receiver(post_save, sender=DeveloperInvitation)
def activity_handler_developer_invitation(sender, instance, created, **kwargs):
    if created:
        send_developer_invited_email.delay(instance.id)
