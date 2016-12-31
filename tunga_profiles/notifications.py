import datetime

from django.contrib.auth import get_user_model
from django_rq.decorators import job

from tunga.settings import EMAIL_SUBJECT_PREFIX, TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS, TUNGA_URL
from tunga_profiles.models import DeveloperApplication, Skill, DeveloperInvitation
from tunga_tasks.models import Task
from tunga_utils.helpers import clean_instance
from tunga_utils.emails import send_mail


@job
def send_new_developer_email(instance):
    instance = clean_instance(instance, DeveloperApplication)
    subject = "%s %s has applied to become a Tunga developer" % (EMAIL_SUBJECT_PREFIX, instance.display_name)
    to = TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS
    ctx = {
        'application': instance,
    }
    send_mail(subject, 'tunga/email/email_new_developer_application', to, ctx)


@job
def send_developer_application_received_email(instance):
    instance = clean_instance(instance, DeveloperApplication)
    subject = "%s Your application to become a Tunga developer has been received" % EMAIL_SUBJECT_PREFIX
    to = [instance.email]
    ctx = {
        'application': instance
    }
    send_mail(subject, 'tunga/email/email_developer_application_received', to, ctx)


@job
def send_developer_accepted_email(instance):
    instance = clean_instance(instance, DeveloperApplication)
    subject = "%s Your application to become a Tunga developer has been accepted" % EMAIL_SUBJECT_PREFIX
    to = [instance.email]
    ctx = {
        'application': instance,
        'invite_url': '%s/signup/developer/%s/' % (TUNGA_URL, instance.confirmation_key)
    }
    if send_mail(subject, 'tunga/email/email_developer_application_accepted', to, ctx):
        instance.confirmation_sent_at = datetime.datetime.utcnow()
        instance.save()


@job
def send_new_skill_email(instance):
    instance = clean_instance(instance, Skill)
    subject = "%s New skill created" % EMAIL_SUBJECT_PREFIX
    to = TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS

    users = get_user_model().objects.filter(userprofile__skills=instance)
    tasks = Task.objects.filter(skills=instance)
    ctx = {
        'skill': instance.name,
        'users': users,
        'tasks': tasks
    }
    send_mail(subject, 'tunga/email/email_new_skill', to, ctx)


@job
def send_developer_invited_email(instance):
    instance = clean_instance(instance, DeveloperInvitation)
    subject = "%s You have been invited to become a Tunga developer" % EMAIL_SUBJECT_PREFIX
    to = [instance.email]
    ctx = {
        'invite': instance,
        'invite_url': '%s/signup/developer/invite/%s/' % (TUNGA_URL, instance.invitation_key)
    }
    if send_mail(subject, 'tunga/email/email_developer_invitation', to, ctx):
        instance.invitation_sent_at = datetime.datetime.utcnow()
        instance.save()

        send_new_developer_invitation_sent_email(instance)


@job
def send_new_developer_invitation_sent_email(instance):
    instance = clean_instance(instance, DeveloperInvitation)
    subject = "%s %s has been invited to become a Tunga developer" % (EMAIL_SUBJECT_PREFIX, instance.first_name)
    to = [instance.created_by.email]
    to.extend(TUNGA_STAFF_UPDATE_EMAIL_RECIPIENTS)
    ctx = {
        'invite': instance
    }
    send_mail(subject, 'tunga/email/email_developer_invitation_sent', to, ctx)


@job
def send_developer_invitation_accepted_email(instance):
    instance = clean_instance(instance, DeveloperInvitation)
    subject = "%s %s has accepted your invitation to become a Tunga developer" % (EMAIL_SUBJECT_PREFIX, instance.first_name)
    to = [instance.created_by.email]
    ctx = {
        'invite': instance
    }
    send_mail(subject, 'tunga/email/email_developer_invitation_accepted', to, ctx)
