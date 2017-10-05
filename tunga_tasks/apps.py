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
            self.get_model('Estimate'), self.get_model('Quote'), self.get_model('Sprint'),
            self.get_model('WorkActivity'), self.get_model('ProgressEvent'), self.get_model('ProgressReport'),
            self.get_model('Integration'), self.get_model('IntegrationEvent'),
            self.get_model('IntegrationMeta'), self.get_model('IntegrationActivity')
        )
