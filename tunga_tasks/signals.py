from actstream.signals import action
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver

from tunga_tasks.models import Task, Application, Participation, TaskRequest


@receiver(post_save, sender=Task)
def activity_handler_new_task(sender, instance, created, **kwargs):
    if created:
        action.send(instance.user, verb='created a task', action_object=instance)
    else:
        update_fields = kwargs.get('update_fields', None)
        if 'assignee' in update_fields and instance.assignee:
            action.send(instance.user, verb='assigned a task to', action_object=instance.assignee, target=instance)


@receiver(post_save, sender=Application)
def activity_handler_new_application(sender, instance, created, **kwargs):
    if created:
        action.send(instance.user, verb='applied for task', action_object=instance, target=instance.task)
    else:
        update_fields = kwargs.get('update_fields', None)
        if 'accepted' in update_fields and instance.accepted:
            action.send(
                    instance.task.user, verb='accepted a task application',
                    action_object=instance, target=instance.task
            )
        elif 'responded' in update_fields and not instance.accepted:
            action.send(
                    instance.task.user, verb='rejected a task application',
                    action_object=instance, target=instance.task
            )


@receiver(post_save, sender=Participation)
def activity_handler_new_participant(sender, instance, created, **kwargs):
    if created:
        action.send(instance.created_by, verb='invited a participant', action_object=instance, target=instance.task)
    else:
        update_fields = kwargs.get('update_fields', None)
        if 'accepted' in update_fields and instance.accepted:
            action.send(
                    instance.task.user, verb='accepted participation',
                    action_object=instance, target=instance.task
            )
        elif 'responded' in update_fields and not instance.accepted:
            action.send(
                    instance.task.user, verb='rejected participation',
                    action_object=instance, target=instance.task
            )


@receiver(post_save, sender=TaskRequest)
def activity_handler_task_request(sender, instance, created, **kwargs):
    if created:
        action.send(
                instance.user, verb='created a %s' % instance.get_type_display().lower(),
                action_object=instance, target=instance.task
        )
