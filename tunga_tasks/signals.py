from actstream.signals import action
from decimal import Decimal
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver, Signal

from tunga_activity import verbs
from tunga_messages.models import Message
from tunga_messages.tasks import get_or_create_task_channel
from tunga_tasks.models import Task, Application, Participation, ProgressEvent, ProgressReport, \
    IntegrationActivity, Integration, Estimate, Quote
from tunga_tasks.notifications import notify_new_task_application, send_new_task_application_applicant_email, \
    send_new_task_invitation_email, send_new_task_application_response_email, notify_task_invitation_response, \
    send_task_application_not_selected_email, notify_new_progress_report, notify_task_approved, send_estimate_status_email
from tunga_tasks.tasks import initialize_task_progress_events, update_task_periodic_updates, \
    complete_harvest_integration
from tunga_utils.constants import APP_INTEGRATION_PROVIDER_HARVEST, STATUS_SUBMITTED, STATUS_APPROVED, STATUS_DECLINED, \
    STATUS_ACCEPTED, STATUS_REJECTED

# Task
task_approved = Signal(providing_args=["task"])
task_applications_closed = Signal(providing_args=["task"])
task_closed = Signal(providing_args=["task"])

# Applications
application_response = Signal(providing_args=["application"])

# Participation
participation_response = Signal(providing_args=["participation"])

# Estimates
estimate_created = Signal(providing_args=["estimate"])
estimate_status_changed = Signal(providing_args=["estimate"])

# Quotes
quote_created = Signal(providing_args=["quote"])
quote_status_changed = Signal(providing_args=["quote"])

# Integrations
task_integration = Signal(providing_args=["integration"])


@receiver(post_save, sender=Task)
def activity_handler_new_task(sender, instance, created, **kwargs):
    if created:
        action.send(instance.user, verb=verbs.CREATE, action_object=instance)

        initialize_task_progress_events.delay(instance.id)


@receiver(task_approved, sender=Task)
def activity_handler_task_approved(sender, task, **kwargs):
    if task.approved and task.is_task:
        notify_task_approved.delay(task.id)


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
            channel = get_or_create_task_channel(instance.user, instance)
            Message.objects.create(channel=channel, **{'user': instance.user, 'body': instance.remarks})

        # Send email notification to project owner
        notify_new_task_application.delay(instance.id)

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

        if application.accepted and application.hours_needed and application.task.is_task:
            task = application.task
            task.bid = Decimal(application.hours_needed)*application.task.dev_rate
            task.save()


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
        notify_task_invitation_response.delay(participation.id)

        if participation.accepted:
            update_task_periodic_updates.delay(participation.task.id)


@receiver(post_save, sender=Estimate)
def activity_handler_estimate(sender, instance, created, **kwargs):
    if created:
        action.send(
                instance.user, verb=verbs.CREATE,
                action_object=instance, target=instance.task
        )


@receiver(post_save, sender=Quote)
def activity_handler_quote(sender, instance, created, **kwargs):
    if created:
        action.send(
                instance.user, verb=verbs.CREATE,
                action_object=instance, target=instance.task
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

        notify_new_progress_report.delay(instance.id)


@receiver(post_save, sender=Integration)
def activity_handler_integration(sender, instance, created, **kwargs):
    if created:
        action.send(instance.created_by, verb=verbs.INTEGRATE, action_object=instance, target=instance.task)


@receiver(post_save, sender=IntegrationActivity)
def activity_handler_integration_activity(sender, instance, created, **kwargs):
    if created:
        action.send(instance.integration, verb=verbs.REPORT, action_object=instance, target=instance.integration.task)


@receiver(task_integration, sender=Integration)
def activity_handler_task_integration(sender, integration, **kwargs):
    if integration.provider == APP_INTEGRATION_PROVIDER_HARVEST:
        complete_harvest_integration.delay(integration.id)


VERB_MAP_STATUS_CHANGE = {
    STATUS_SUBMITTED: verbs.SUBMIT,
    STATUS_APPROVED: verbs.APPROVE,
    STATUS_DECLINED: verbs.DECLINE,
    STATUS_ACCEPTED: verbs.ACCEPT,
    STATUS_REJECTED: verbs.REJECT,
}


@receiver(estimate_status_changed, sender=Estimate)
def activity_handler_estimate_status_changed(sender, estimate, **kwargs):
    action_verb = VERB_MAP_STATUS_CHANGE.get(estimate.status, None)
    if action_verb:
        action_user = estimate
        if estimate.status == STATUS_SUBMITTED:
            action_user = estimate.user
        elif estimate.status in [STATUS_APPROVED, STATUS_DECLINED]:
            action_user = estimate.moderated_by
        elif estimate.status in [STATUS_ACCEPTED, STATUS_REJECTED]:
            action_user = estimate.reviewed_by
        action.send(action_user or estimate, verb=action_verb, action_object=estimate, target=estimate.task)

    send_estimate_status_email(estimate.id)


@receiver(quote_status_changed, sender=Quote)
def activity_handler_quote_status_changed(sender, quote, **kwargs):
    action_verb = VERB_MAP_STATUS_CHANGE.get(quote.status, None)
    if action_verb:
        action_user = quote
        if quote.status == STATUS_SUBMITTED:
            action_user = quote.user
        elif quote.status in [STATUS_APPROVED, STATUS_DECLINED]:
            action_user = quote.moderated_by
        elif quote.status in [STATUS_ACCEPTED, STATUS_REJECTED]:
            action_user = quote.reviewed_by
        action.send(action_user or quote, verb=action_verb, action_object=quote, target=quote.task)

    if quote.status == STATUS_ACCEPTED:
        task = quote.task
        task.approved = True
        task.bid = quote.fee
        task.save()

    send_estimate_status_email(quote.id, estimate_type='quote')


