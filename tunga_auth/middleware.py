from django.utils import timezone


class UserLastActivityMiddleware(object):

    def process_response(self, request, response):
        assert hasattr(request, 'user'), 'No user object defined for this request.'
        if request.user.is_authenticated():
            request.user.last_activity = timezone.now()
            request.user.save()
        return response
