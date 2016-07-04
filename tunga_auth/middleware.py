import datetime


class UserLastActivityMiddleware(object):

    def process_response(self, request, response):
        try:
            if request.user.is_authenticated():
                request.user.last_activity = datetime.datetime.utcnow()
                request.user.save()
        except AttributeError:
            pass
        return response
