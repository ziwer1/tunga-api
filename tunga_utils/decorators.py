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
    A decorator to convert the first argument of the function into an instance of the declared model
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


def object_id_only_comparable(klass):
    """
    A decorator that defines __eq__ , __ne__ and __hash__ that allow object comparisons strictly based on id attribute
    """

    klass.__eq__ = lambda self, other: isinstance(other, klass) and self.id == other.id
    klass.__ne__ = lambda self, other: not self.__eq__(other)
    klass.__hash__ = lambda self: hash(self.id)
    return klass
