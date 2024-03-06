from functools import wraps

EXPOSED_FUNCTIONS = {}


def func2code(func):
    """
    Python by default does not allow to compare functions. This is a workaround.
    """
    return func.__code__.co_code


def test_function_equality(f1, f2):
    return func2code(f1) == func2code(f2)


def expose_to_api(endpoint):
    def decorator(f):
        assert "/" not in endpoint, "Endpoint cannot contain '/'"

        is_static = isinstance(f, staticmethod)
        if is_static:
            f = f.__func__
        is_normal_function = (
            str(type(f)) == "<class 'function'>" and len(f.__qualname__.split(".")) == 1
        )

        if not (is_static or is_normal_function):
            raise TypeError(
                "API function must be staticmethod or regular function, but it cannot be a regular method of a class or a classmethod"
            )
        if endpoint in EXPOSED_FUNCTIONS:
            assert test_function_equality(
                EXPOSED_FUNCTIONS[endpoint], f
            ), "Endpoint already registered"
        EXPOSED_FUNCTIONS[endpoint] = f

        @wraps(f)
        def wrapper(*args, **kwargs):
            return f(*args, **kwargs)

        return wrapper

    return decorator
