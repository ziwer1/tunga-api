from actstream.signals import action
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver, Signal

from tunga_activity import verbs
from tunga_messages.tasks import create_channel
from tunga_tasks.emails import send_new_task_application_email, send_new_task_application_applicant_email, \
    send_new_task_invitation_email, send_new_task_application_response_email, send_new_task_invitation_response_email, \
    send_task_application_not_selected_email, send_new_progress_report_email
from tunga_tasks.models import Task, Application, Participation, TaskRequest, ProgressEvent, ProgressReport, \
    IntegrationActivity, Integration
from tunga_tasks.tasks import initialize_task_progress_events, update_task_periodic_updates

task_applications_closed = Signal(providing_args=["task"])

task_closed = Signal(providing_args=["task"])

application_response = Signal(providing_args=["application"])

participation_response = Signal(providing_args=["participation"])


@receiver(post_save, sender=Task)
def activity_handler_new_task(sender, instance, created, **kwargs):
    if created:
        action.send(instance.user, verb=verbs.CREATE, action_object=instance)

        initialize_task_progress_events.delay(instance.id)


@receiver(task_applications_closed, sender=Task)
def activity_handler_task_applications_closed(sender, task, **kwargs):
    if not task.apply:
        action.send(task.user, verb=verbs.CLOSE_APPLY, target=task)

        send_task_application_not_selected_email.delay(task.id)


@receiver(task_closed, sender=Task)
def activity_handler_task_closed(sender, task, **kwargs):
    if task.closed:
        action.send(task.user, verb=verbs.CLOSE, target=task)


@receiver(post_save, sender=Application)
def activity_handler_new_application(sender, instance, created, **kwargs):
    if created:
        action.send(instance.user, verb=verbs.APPLY, action_object=instance, target=instance.task)

        if instance.remarks:
            # Send the developer's remarks as a message to the client
            subject = 'Developer comment on %s' % instance.task.summary
            create_channel(
                initiator=instance.user, participants=[instance.task.user],
                subject=subject, messages=[{'user': instance.user, 'body': instance.remarks}],
                content_object=instance
            )

        # Send email notification to project owner
        send_new_task_application_email.delay(instance.id)

        # Send email confirmation to applicant
        send_new_task_application_applicant_email.delay(instance.id)


@receiver(application_response, sender=Application)
def activity_handler_application_response(sender, application, **kwargs):
    if application.accepted or application.responded:
        status_verb = application.accepted and verbs.ACCEPT or verbs.REJECT
        action.send(
            application.task.user, verb=status_verb, action_object=application, target=application.task
        )
        send_new_task_application_response_email.delay(application.id)


@receiver(post_save, sender=Participation)
def activity_handler_new_participant(sender, instance, created, **kwargs):
    if created:
        action.send(instance.created_by, verb=verbs.ADD, action_object=instance, target=instance.task)

        if not instance.responded and not instance.accepted:
            send_new_task_invitation_email.delay(instance.id)

        if instance.accepted:
            update_task_periodic_updates.delay(instance.task.id)


@receiver(participation_response, sender=Participation)
def activity_handler_participation_response(sender, participation, **kwargs):
    if participation.accepted or participation.responded:
        status_verb = participation.accepted and verbs.ACCEPT or verbs.REJECT
        action.send(
            participation.task.user, verb=status_verb, action_object=participation, target=participation.task
        )
        send_new_task_invitation_response_email.delay(participation.id)

        if participation.accepted:
            update_task_periodic_updates.delay(participation.task.id)


@receiver(post_save, sender=TaskRequest)
def activity_handler_task_request(sender, instance, created, **kwargs):
    if created:
        action.send(
                instance.user, verb=verbs.REQUEST, action_object=instance, target=instance.task
        )


@receiver(post_save, sender=ProgressEvent)
def activity_handler_progress_event(sender, instance, created, **kwargs):
    if created:
        action.send(
                instance.created_by or instance.task.user, verb=verbs.CREATE,
                action_object=instance, target=instance.task
        )


@receiver(post_save, sender=ProgressReport)
def activity_handler_progress_report(sender, instance, created, **kwargs):
    if created:
        action.send(instance.user, verb=verbs.REPORT, action_object=instance, target=instance.event)

        send_new_progress_report_email(instance.id)


@receiver(post_save, sender=Integration)
def activity_handler_integration(sender, instance, created, **kwargs):
    if created:
        action.send(instance.created_by, verb=verbs.INTEGRATE, action_object=instance, target=instance.task)


@receiver(post_save, sender=IntegrationActivity)
def activity_handler_integration_activity(sender, instance, created, **kwargs):
    if created:
        action.send(instance.integration, verb=verbs.REPORT, action_object=instance, target=instance.integration.task)
