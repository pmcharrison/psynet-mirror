import json
import inspect
from functools import reduce
from sqlalchemy.sql import func

def get_arg_from_dict(x, desired: str, use_default = False, default = None):
    if desired not in x:
        if use_default:
            return default
        else:
            raise ValueError
    return x[desired]

def sql_sample_one(x):
    return x.order_by(func.random()).first()

# def get_json_arg_from_request(request, desired: str, use_default = False, default = None):
#     arguments = request.json
#     if arguments is None:
#         if use_default:
#             return default
#         else:
#             raise APIMissingJSON
#     elif desired not in arguments:
#         if use_default:
#             return default
#         else:
#             raise APIArgumentError
#     return arguments[desired]

# class APIArgumentError(ValueError):
#     pass

# class APIMissingJSON(ValueError):
#     pass

def dict_to_js_vars(x):
    y = [f"var {key} = JSON.parse('{json.dumps(value)}'); " for key, value in x.items()]
    return reduce(lambda a, b: a + b, y )

def call_function(function, args: dict):
    requested_args = get_function_args(function)
    arg_values = [args[requested] for requested in requested_args]
    return function(*arg_values)

def get_function_args(f):
    return [str(x) for x in inspect.signature(f).parameters]

def check_function_args(f, args, exact=True):
    if not callable(f):
        raise TypeError("<f> is not a function (but it should be).")
    actual = [str(x) for x in inspect.signature(f).parameters]
    if exact:
        if actual != list(args):
            raise ValueError(f"Invalid argument list: {actual}")
    else:
        for a in actual:
            if a not in args:
                raise ValueError(f"Invalid argument: {a}")
    return True

    