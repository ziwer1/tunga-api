from __future__ import unicode_literals

from django.apps import AppConfig


class TungaMessagesConfig(AppConfig):
    name = 'tunga_messages'
    verbose_name = 'Messages'

    def ready(self):
        from actstream import registry
        from tunga_messages import signals

        registry.register(self.get_model('Message'))
