from django.contrib.auth import get_user_model
from django_rq.decorators import job

from tunga.settings import TUNGA_URL, SLACK_STAFF_INCOMING_WEBHOOK, \
    TUNGA_ICON_URL_150, SLACK_ATTACHMENT_COLOR_TUNGA, SLACK_STAFF_CUSTOMER_CHANNEL
from tunga_messages.models import Message
from tunga_utils import slack_utils
from tunga_utils.constants import CHANNEL_TYPE_SUPPORT, APP_INTEGRATION_PROVIDER_SLACK, CHANNEL_TYPE_DEVELOPER, \
    USER_TYPE_DEVELOPER
from tunga_utils.emails import send_mail
from tunga_utils.helpers import clean_instance


@job
def notify_new_message(instance):
    notify_new_message_email.delay(instance)
    notify_new_message_slack.delay(instance)


@job
def notify_new_message_email(instance):
    instance = clean_instance(instance, Message)
    to = []
    recipients = instance.channel.participants.all()
    if recipients:
        to = [recipient.email for recipient in recipients]
    if to and isinstance(to, (list, tuple)):
        subject = "New message from {}".format(instance.sender.short_name)
        ctx = {
            'sender': instance.sender.short_name,
            'subject': instance.channel.subject,
            'channel': instance.channel,
            'message': instance,
            'message_url': '%s/conversation/%s/' % (TUNGA_URL, instance.channel_id)
        }
        send_mail(subject, 'tunga/email/new_message', to, ctx)


@job
def notify_new_message_slack(instance):
    instance = clean_instance(instance, Message)
    if instance.channel.type == CHANNEL_TYPE_SUPPORT and instance.source != APP_INTEGRATION_PROVIDER_SLACK:
        if instance.user and (instance.user.is_staff or instance.user.is_superuser):
            # Ignore messages from admins
            return
        channel_url = '%s/help/%s/' % (TUNGA_URL, instance.channel_id)
        message_details = {
            slack_utils.KEY_AUTHOR_NAME: instance.sender.display_name,
            slack_utils.KEY_TEXT: instance.text_body,
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT, slack_utils.KEY_FOOTER],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_TUNGA,
            slack_utils.KEY_FOOTER: 'Type C{} <your reply here>'.format(instance.channel_id),
            slack_utils.KEY_FOOTER_ICON: TUNGA_ICON_URL_150,
        }
        if instance.channel.subject:
            message_details[slack_utils.KEY_TITLE] = instance.channel.subject
            message_details[slack_utils.KEY_TITLE_LINK] = channel_url
        else:
            inquirer = instance.channel.get_inquirer()
            if inquirer:
                try:
                    message_details[slack_utils.KEY_TITLE] = 'Help{}{}'.format(
                        inquirer.name and ': ' or '', inquirer.name or ''
                    )
                    if inquirer.email:
                        message_details[slack_utils.KEY_TEXT] += '\n\nEmail: {}'.format(inquirer.email)
                    message_details[slack_utils.KEY_TITLE_LINK] = channel_url
                except:
                    pass

        if instance.user:
            message_details[slack_utils.KEY_AUTHOR_LINK] = '%s/people/%s/' % (TUNGA_URL, instance.user.username)
        try:
            if instance.sender.avatar_url:
                message_details[slack_utils.KEY_AUTHOR_ICON] = instance.sender.avatar_url
        except:
            pass

        slack_msg = {
            slack_utils.KEY_TEXT: "New message from {} | <{}|View on Tunga>".format(
                instance.sender.short_name, channel_url
            ),
            slack_utils.KEY_CHANNEL: SLACK_STAFF_CUSTOMER_CHANNEL,
            slack_utils.KEY_ATTACHMENTS: [
                message_details
            ],
        }
        slack_utils.send_incoming_webhook(SLACK_STAFF_INCOMING_WEBHOOK, slack_msg)


@job
def notify_new_message_developers(instance):
    instance = clean_instance(instance, Message)

    if instance.channel.type == CHANNEL_TYPE_DEVELOPER and (instance.user.is_staff or instance.user.is_superuser) and \
            not instance.channel.messages.filter(user__is_staff=False, user__is_superuser=False).count():
        recipients = get_user_model().objects.filter(type=USER_TYPE_DEVELOPER)
        if recipients:
            to = [recipients[0]]
            bcc = recipients[1:] if len(recipients) > 1 else None

            if to and isinstance(to, (list, tuple)):
                subject = "Developer Notification: {}".format(
                    instance.channel.subject or instance.sender.short_name
                )
                ctx = {
                    'sender': instance.sender.short_name,
                    'subject': instance.channel.subject,
                    'channel': instance.channel,
                    'message': instance,
                    'message_url': '%s/conversation/%s/' % (TUNGA_URL, instance.channel_id)
                }
                send_mail(subject, 'tunga/email/new_message', to, ctx, bcc=bcc)
