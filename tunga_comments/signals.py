from actstream.signals import action
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver

from tunga_activity import verbs
from tunga_comments.models import Comment


@receiver(post_save, sender=Comment)
def activity_handler_comment(sender, instance, created, **kwargs):
    if created:
        action.send(instance.user, verb=verbs.COMMENT, action_object=instance, target=instance.content_object)

