from __future__ import unicode_literals

from django.apps import AppConfig


class TungaTasksConfig(AppConfig):
    name = 'tunga_tasks'
    verbose_name = 'Tasks'

    def ready(self):
        from actstream import registry
        from tunga_tasks import signals

        registry.register(
            self.get_model('Task'), self.get_model('Application'), self.get_model('Participation'),
            self.get_model('TaskRequest'), self.get_model('ProgressEvent'), self.get_model('ProgressReport')
        )
