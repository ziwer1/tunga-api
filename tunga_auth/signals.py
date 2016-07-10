from allauth.account.models import EmailAddress
from allauth.account.signals import user_signed_up
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver

from tunga_auth.emails import send_new_user_email


@receiver(post_save, sender=get_user_model())
def user_add_email_to_all_auth_handler(sender, instance, created, **kwargs):
    if created:
        if instance.email:
            if instance.is_superuser or instance.is_staff:
                email_address = EmailAddress.objects.add_email(None, instance, instance.email)
                email_address.verified = True
                email_address.primary = True
                email_address.save()


@receiver(user_signed_up)
def new_user_signup_handler(request, user, **kwargs):
    send_new_user_email.delay(user.id)
