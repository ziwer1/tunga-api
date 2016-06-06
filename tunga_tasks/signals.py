import datetime

from actstream.signals import action
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver

from tunga_tasks.emails import send_new_task_application_email, send_new_task_application_applicant_email, \
    send_new_task_invitation_email, send_new_task_application_response_email
from tunga_tasks.models import Task, Application, Participation, TaskRequest


@receiver(post_save, sender=Task)
def activity_handler_new_task(sender, instance, created, **kwargs):
    if created:
        action.send(instance.user, verb='created a task', action_object=instance)
    else:
        update_fields = kwargs.get('update_fields', None)
        if update_fields:
            if 'closed' in update_fields and instance.closed:
                instance.closed_at = datetime.datetime.utcnow()
                instance.save()
            if 'paid' in update_fields and instance.paid:
                instance.paid_at = datetime.datetime.utcnow()
                instance.save()


@receiver(post_save, sender=Application)
def activity_handler_new_application(sender, instance, created, **kwargs):
    if created:
        action.send(instance.user, verb='applied for task', action_object=instance, target=instance.task)

        # Send email notification to project owner
        send_new_task_application_email(instance)

        # Send email confirmation to applicant
        send_new_task_application_applicant_email(instance)
    else:
        update_fields = kwargs.get('update_fields', None)
        if update_fields:
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

        if instance.responded:
            if instance.accepted:
                send_new_task_application_response_email(instance, accepted=True)
        else:
            send_new_task_invitation_email(instance)
    else:
        update_fields = kwargs.get('update_fields', None)
        if update_fields:
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
