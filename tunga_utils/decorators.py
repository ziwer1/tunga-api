from functools import wraps


def catch_all_exceptions(func):
    """
    This decorator is used to abstract the try except block for functions that don't affect the final status of an action.
    """

    @wraps(func)
    def func_wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except:
            pass

    return func_wrapper
