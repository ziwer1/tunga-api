import datetime

from django.utils.deprecation import MiddlewareMixin


class UserLastActivityMiddleware(MiddlewareMixin):

    def process_response(self, request, response):
        try:
            if request.user.is_authenticated():
                request.user.last_activity_at = datetime.datetime.utcnow()
                request.user.save()
        except AttributeError:
            pass
        return response
