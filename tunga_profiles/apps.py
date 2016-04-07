from __future__ import unicode_literals

from django.apps import AppConfig


class TungaProfilesConfig(AppConfig):
    name = 'tunga_profiles'
    verbose_name = 'Profiles'

    def ready(self):
        from actstream import registry
        from tunga_profiles import signals

        registry.register(self.get_model('Connection'))
