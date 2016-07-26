from __future__ import unicode_literals

from django.apps import AppConfig


class TungaUtilsConfig(AppConfig):
    name = 'tunga_utils'
    verbose_name = 'Utilities'

    def ready(self):
        from actstream import registry
        from tunga_utils import signals

        registry.register(self.get_model('Upload'))
