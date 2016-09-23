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


def convert_first_arg_to_instance(model):
    """
    Convert the first argument of the function into an instance of the declared model
    """

    def real_decorator(func):
        def func_wrapper(*args, **kwargs):
            if model and len(args):
                param = args[0]
                if isinstance(param, model):
                    func(*args, **kwargs)
                else:
                    try:
                        instance = model.objects.get(id=param)
                    except:
                        instance = model(id=param)
                    func(instance, *args[1:], **kwargs)
            else:
                func(*args, **kwargs)
        return func_wrapper
    return real_decorator
