from __future__ import unicode_literals

from django.apps import AppConfig


class TungaUtilsConfig(AppConfig):
    name = 'tunga_utils'
    verbose_name = 'Utilities'

    def ready(self):
        from tunga_utils import signals
