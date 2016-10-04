from django_rq.decorators import job

from tunga.settings import EMAIL_SUBJECT_PREFIX, TUNGA_URL, SLACK_CUSTOMER_INCOMING_WEBHOOK, SLACK_CUSTOMER_BOT_NAME, \
    SLACK_ATTACHMENT_COLOR_GREEN, TUNGA_ICON_URL_150
from tunga_messages.models import Message
from tunga_settings.slugs import DIRECT_MESSAGES_EMAIL
from tunga_utils import slack_utils
from tunga_utils.constants import CHANNEL_TYPE_SUPPORT, APP_INTEGRATION_PROVIDER_SLACK
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
        subject = "%s New message from %s" % (EMAIL_SUBJECT_PREFIX, instance.sender.short_name)
        ctx = {
            'sender': instance.sender.short_name,
            'subject': instance.channel.subject,
            'channel': instance.channel,
            'message': instance,
            'message_url': '%s/channel/%s/' % (TUNGA_URL, instance.channel_id)
        }
        send_mail(subject, 'tunga/email/email_new_message', to, ctx)


@job
def notify_new_message_slack(instance):
    instance = clean_instance(instance, Message)
    if instance.channel.type == CHANNEL_TYPE_SUPPORT and instance.source != APP_INTEGRATION_PROVIDER_SLACK:
        if instance.user and (instance.user.is_staff or instance.user.is_superuser):
            # Ignore messages from admins
            return
        channel_url = '%s/help/%s/' % (TUNGA_URL, instance.channel_id)
        summary = "New message from %s" % instance.sender.short_name
        message_details = {
            slack_utils.KEY_PRETEXT: summary,
            slack_utils.KEY_AUTHOR_NAME: instance.sender.display_name,
            slack_utils.KEY_TEXT: '%s\n\n<%s|View on Tunga>' % (instance.text_body, channel_url),
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT, slack_utils.KEY_FOOTER],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_GREEN,
            slack_utils.KEY_FOOTER: 'Tunga | Type C%s <your reply here>' % instance.channel_id,
            slack_utils.KEY_FOOTER_ICON: TUNGA_ICON_URL_150,
            slack_utils.KEY_FALLBACK: summary,
        }
        if instance.channel.subject:
            message_details[slack_utils.KEY_TITLE] = instance.channel.subject
            message_details[slack_utils.KEY_TITLE_LINK] = channel_url
        else:
            inquirer = instance.channel.get_inquirer()
            if inquirer:
                try:
                    message_details[slack_utils.KEY_TITLE] = 'Help: %s' % inquirer.name
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
            slack_utils.KEY_ATTACHMENTS: [
                message_details
            ],
        }
        slack_utils.send_incoming_webhook(SLACK_CUSTOMER_INCOMING_WEBHOOK, slack_msg)
