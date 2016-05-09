from functools import wraps

from rest_framework.filters import DjangoFilterBackend, SearchFilter

DEFAULT_FILTER_BACKENDS = (DjangoFilterBackend, SearchFilter)


def dont_filter_staff_or_superuser(func):
    """
    This decorator is used to abstract common is_staff and is_superuser functionality
    out of filtering. It determines which parameter is the request based on name.
    """

    @wraps(func)
    def func_wrapper(*args, **kwargs):
        request = args[1]
        queryset = args[2]

        if request.user.is_staff or request.user.is_superuser:
            return queryset

        return func(*args, **kwargs)

    return func_wrapper
