from __future__ import unicode_literals

from django.apps import AppConfig


class TungaAuthConfig(AppConfig):
    name = 'tunga_auth'
    verbose_name = 'Authentication'

    def ready(self):
        from actstream import registry
        from tunga_auth import signals

        registry.register(self.get_model('TungaUser'))

