import hashlib
import importlib
import importlib.util
import inspect
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from functools import reduce, wraps
from urllib.parse import ParseResult, urlparse

import pandas as pd
from dallinger.config import get_config
from sqlalchemy.sql import func


def get_logger():
    logging.basicConfig(level=logging.INFO)
    return logging.getLogger()


logger = get_logger()


def get_arg_from_dict(x, desired: str, use_default=False, default=None):
    if desired not in x:
        if use_default:
            return default
        else:
            raise KeyError
    return x[desired]


def sql_sample_one(x):
    return x.order_by(func.random()).first()


def import_local_experiment():
    # Imports experiment.py and returns a dict consisting of
    # 'package' which corresponds to the experiment *package*,
    # 'module' which corresponds to the experiment *module*, and
    # 'class' which corresponds to the experiment *class*.
    # It also adds the experiment directory to sys.path, meaning that any other
    # modules defined there can be imported using ``import``.
    # import pdb; pdb.set_trace()
    get_config()

    import dallinger.experiment

    dallinger.experiment.load()

    dallinger_experiment = sys.modules.get("dallinger_experiment")
    sys.path.append(os.getcwd())

    try:
        module = dallinger_experiment.experiment
    except AttributeError as e:
        raise Exception(
            f"Possible ModuleNotFoundError in your experiment's experiment.py file. "
            f'Please check your imports!\nOriginal error was "AttributeError: {e}"'
        )

    return {
        "package": dallinger_experiment,
        "module": module,
        "class": dallinger.experiment.load(),
    }


# def import_local_experiment():
#     sys.path.append(os.getcwd())
#     import experiment

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
    return reduce(lambda a, b: a + b, y)


def call_function(function, args: dict):
    requested_args = get_function_args(function)
    arg_values = [args[requested] for requested in requested_args]
    return function(*arg_values)


def get_function_args(f):
    return [str(x) for x in inspect.signature(f).parameters]


def check_function_args(f, args, need_all=True):
    if not callable(f):
        raise TypeError("<f> is not a function (but it should be).")
    actual = [str(x) for x in inspect.signature(f).parameters]
    if need_all:
        if actual != list(args):
            raise ValueError(f"Invalid argument list: {actual}")
    else:
        for a in actual:
            if a not in args:
                raise ValueError(f"Invalid argument: {a}")
    return True


def get_object_from_module(module_name: str, object_name: str):
    """
    Finds and returns an object from a module.

    Parameters
    ----------

    module_name
        The name of the module.

    object_name
        The name of the object.
    """
    mod = importlib.import_module(module_name)
    obj = getattr(mod, object_name)
    return obj


def log_time_taken(fun):
    @wraps(fun)
    def wrapper(*args, **kwargs):
        start_time = time.monotonic()
        res = fun(*args, **kwargs)
        end_time = time.monotonic()
        time_taken = end_time - start_time
        logger.info("Time taken by %s: %.3f seconds.", fun.__name__, time_taken)
        return res

    return wrapper


def negate(f):
    """
    Negates a function.

    Parameters
    ----------

    f
        Function to negate.
    """

    @wraps(f)
    def g(*args, **kwargs):
        return not f(*args, **kwargs)

    return g


def linspace(lower, upper, length: int):
    """
    Returns a list of equally spaced numbers between two closed bounds.

    Parameters
    ----------

    lower : number
        The lower bound.

    upper : number
        The upper bound.

    length : int
        The length of the resulting list.
    """
    return [lower + x * (upper - lower) / (length - 1) for x in range(length)]


def merge_dicts(*args, overwrite: bool):
    """
    Merges a collection of dictionaries, with later dictionaries
    taking precedence when the same key appears twice.

    Parameters
    ----------

    *args
        Dictionaries to merge.

    overwrite
        If ``True``, when the same key appears twice in multiple dictionaries,
        the key from the latter dictionary takes precedence.
        If ``False``, an error is thrown if such duplicates occur.
    """

    if len(args) == 0:
        return {}
    return reduce(lambda x, y: merge_two_dicts(x, y, overwrite), args)


def merge_two_dicts(x: dict, y: dict, overwrite: bool):
    """
    Merges two dictionaries.

    Parameters
    ----------

    x :
        First dictionary.

    y :
        Second dictionary.

    overwrite :
        If ``True``, when the same key appears twice in the two dictionaries,
        the key from the latter dictionary takes precedence.
        If ``False``, an error is thrown if such duplicates occur.
    """

    if not overwrite:
        for key in y.keys():
            if key in x:
                raise DuplicateKeyError(
                    f"Duplicate key {key} found in the dictionaries to be merged."
                )

    return {**x, **y}


class DuplicateKeyError(ValueError):
    pass


def corr(x: list, y: list, method="pearson"):
    df = pd.DataFrame({"x": x, "y": y}, columns=["x", "y"])
    return float(df.corr(method=method).at["x", "y"])


class DisableLogger:
    def __enter__(self):
        logging.disable(logging.CRITICAL)

    def __exit__(self, a, b, c):
        logging.disable(logging.NOTSET)


def query_yes_no(question, default="yes"):
    """Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is True for "yes" or False for "no".
    """
    valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = input().lower()
        if default is not None and choice == "":
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' " "(or 'y' or 'n').\n")


def hash_object(x):
    return hashlib.md5(json.dumps(x).encode("utf-8")).hexdigest()


def import_module(name, source):
    spec = importlib.util.spec_from_file_location(name, source)
    foo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(foo)


def serialise_datetime(x):
    if x is None:
        return None
    return x.isoformat()


def unserialise_datetime(x):
    if x is None:
        return None
    return datetime.fromisoformat(x)


def clamp(x):
    return max(0, min(x, 255))


def rgb_to_hex(r, g, b):
    return "#{0:02x}{1:02x}{2:02x}".format(
        clamp(round(r)), clamp(round(g)), clamp(round(b))
    )


def serialise(obj):
    """Serialise objects not serialisable by default"""

    if isinstance(obj, (datetime)):
        return serialise_datetime(obj)
    raise TypeError("Type %s is not serialisable" % type(obj))


def format_datetime_string(datetime_string):
    return datetime.strptime(datetime_string, "%Y-%m-%dT%H:%M:%S.%f").strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def model_name_to_snake_case(model_name):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", model_name).lower()


def json_to_data_frame(json_data):
    columns = []
    for row in json_data:
        [columns.append(key) for key in row.keys() if key not in columns]

    data_frame = pd.DataFrame.from_records(json_data, columns=columns)
    return data_frame


def strip_url_parameters(url):
    parse_result = urlparse(url)
    return ParseResult(
        scheme=parse_result.scheme,
        netloc=parse_result.netloc,
        path=parse_result.path,
        params=None,
        query=None,
        fragment=None,
    ).geturl()
