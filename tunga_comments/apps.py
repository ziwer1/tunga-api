from __future__ import unicode_literals

from django.apps import AppConfig


class TungaCommentsConfig(AppConfig):
    name = 'tunga_comments'
    verbose_name = 'Comments'

    def ready(self):
        from actstream import registry
        from tunga_comments import signals

        registry.register(self.get_model('Comment'))
