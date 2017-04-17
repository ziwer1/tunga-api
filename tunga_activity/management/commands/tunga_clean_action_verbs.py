import six
from actstream.models import Action
from django.core.management.base import BaseCommand
from django.db.models.query_utils import Q

from tunga_activity import verbs


class Command(BaseCommand):

    def handle(self, *args, **options):
        """
        Clean old action verbs
        """
        # command to run: python manage.py tunga_clean_action_verbs

        verb_map = {
            verbs.COMMENT: 'commented',
            verbs.CONNECT: 'made a connection request',
            verbs.ACCEPT: [
                'accepted a connection request', 'accepted a task application', 'True a task application',
                'accepted a task invitation', 'True a task invitation', 'accepted participation'
            ],
            verbs.REJECT: [
                'rejected a connection request', 'rejected a task application', 'rejected a task invitation',
                'rejected participation'
            ],
            verbs.CREATE: ['created a task', 'created a progress event'],
            verbs.CLOSE: 'task closed',
            verbs.CLOSE_APPLY: ['task applications closed', 'close-apply'],
            verbs.APPLY: 'applied for task',
            verbs.ADD: ['added a participant', 'invited a participant'],
            verbs.REQUEST: ['created a close request', 'created a payment request'],
            verbs.INTEGRATE: 'new integration',
            verbs.REPORT: ['created a progress report', 'new integration activity']
        }

        for new_verb, old_verbs in six.iteritems(verb_map):
            if isinstance(old_verbs, list):
                q_filter = Q(verb=old_verbs[0])
                for old_verb in old_verbs[1:]:
                    q_filter = q_filter | Q(verb=old_verb)
            else:
                q_filter = Q(verb=old_verbs)
            r = Action.objects.filter(q_filter).update(verb=new_verb)
            print (r, new_verb)
