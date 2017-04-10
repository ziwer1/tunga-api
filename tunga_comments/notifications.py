from django.contrib.contenttypes.models import ContentType
from django_rq.decorators import job

from tunga.settings import TUNGA_URL
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
    if not slack_utils.is_task_notification_enabled(task, slugs.EVENT_COMMUNICATION):
        return

    task_url = '{}/work/{}/'.format(TUNGA_URL, task.id)

    slack_msg = '{} | <{}|View on Tunga>'.format(instance.text_body, task_url)
    extras = dict(author_name=instance.user.display_name)

    try:
        if instance.user.avatar_url:
            extras['author_icon'] = instance.user.avatar_url
    except:
        pass

    slack_utils.send_integration_message(instance.content_object, message=slack_msg, **extras)
