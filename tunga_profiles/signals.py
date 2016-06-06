from actstream.signals import action
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver

from tunga_profiles.models import Connection


@receiver(post_save, sender=Connection)
def activity_handler_new_connection(sender, instance, created, **kwargs):
    if created:
        action.send(
            instance.from_user, verb='made a connection request', action_object=instance, target=instance.to_user)
    else:
        update_fields = kwargs.get('update_fields', None)
        if update_fields:
            if 'accepted' in update_fields and instance.accepted:
                action.send(instance.to_user, verb='accepted a connection request', action_object=instance)
            elif 'responded' in update_fields and not instance.accepted:
                action.send(instance.to_user, verb='rejected a connection request', action_object=instance)
