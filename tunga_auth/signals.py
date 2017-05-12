from allauth.account.models import EmailAddress
from allauth.account.signals import user_signed_up
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver

from tunga_auth.models import EmailVisitor
from tunga_auth.notifications import send_new_user_email
from tunga_auth.tasks import sync_hubspot_contact, sync_hubspot_email, subscribe_new_user_to_mailing_list
from tunga_utils.constants import USER_TYPE_PROJECT_OWNER, USER_SOURCE_TASK_WIZARD


@receiver(post_save, sender=get_user_model())
def user_add_email_to_all_auth_handler(sender, instance, created, **kwargs):
    if created:
        is_admin = instance.is_superuser or instance.is_staff
        if instance.email and is_admin or instance.source == USER_SOURCE_TASK_WIZARD:
            email_address = EmailAddress.objects.add_email(
                None, instance, instance.email
            )
            if is_admin:
                email_address.verified = True
                email_address.primary = True
                email_address.save()


@receiver(user_signed_up)
def new_user_signup_handler(request, user, **kwargs):
    send_new_user_email.delay(user.id)

    if user.type == USER_TYPE_PROJECT_OWNER:
        sync_hubspot_contact.delay(user.id)

    subscribe_new_user_to_mailing_list.delay(user.id)


@receiver(post_save, sender=EmailVisitor)
def new_email_visitor_handler(sender, instance, created, **kwargs):
    if created:
        sync_hubspot_email.delay(instance.email)
