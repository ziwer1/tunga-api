from django.contrib.contenttypes.models import ContentType
from django_rq.decorators import job

from tunga.settings import TUNGA_URL, TUNGA_ICON_URL_150, SLACK_ATTACHMENT_COLOR_TUNGA, TUNGA_NAME
from tunga_comments.models import Comment
from tunga_tasks import slugs
from tunga_tasks.models import Task
from tunga_utils import slack_utils
from tunga_utils.helpers import clean_instance

@job
def notify_new_comment_slack(instance):
    instance = clean_instance(instance, Comment)

    if ContentType.objects.get_for_model(Task) != ContentType.objects.get_for_model(instance.content_object):
        return

    task = instance.content_object
    if not slack_utils.is_task_notification_enabled(task, slugs.EVENT_COMMENT):
        return

    webhook_url = slack_utils.get_webhook_url(task.user)
    if webhook_url:
        task_url = '%s/task/%s/' % (TUNGA_URL, task.id)
        message_details = {
            slack_utils.KEY_PRETEXT: "New message from %s" % instance.user.short_name,
            slack_utils.KEY_AUTHOR_NAME: instance.user.display_name,
            slack_utils.KEY_TITLE: task.summary,
            slack_utils.KEY_TITLE_LINK: task_url,
            slack_utils.KEY_TEXT: '%s\n\n<%s|View on Tunga>' % (instance.text_body, task_url),
            slack_utils.KEY_MRKDWN_IN: [slack_utils.KEY_TEXT, slack_utils.KEY_FOOTER],
            slack_utils.KEY_COLOR: SLACK_ATTACHMENT_COLOR_TUNGA,
            slack_utils.KEY_FOOTER: TUNGA_NAME,
            slack_utils.KEY_FOOTER_ICON: TUNGA_ICON_URL_150,
            slack_utils.KEY_FALLBACK: "New message from %s: %s" % (instance.user.short_name, instance.text_body),
        }

        if instance.user:
            message_details[slack_utils.KEY_AUTHOR_LINK] = '%s/people/%s/' % (TUNGA_URL, instance.user.username)
        try:
            if instance.user.avatar_url:
                message_details[slack_utils.KEY_AUTHOR_ICON] = instance.user.avatar_url
        except:
            pass
        slack_msg = {
            slack_utils.KEY_ATTACHMENTS: [
                message_details
            ]
        }
        slack_utils.send_incoming_webhook(webhook_url, slack_msg)
