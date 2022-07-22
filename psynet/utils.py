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

import pexpect
from dallinger import db
from dallinger.config import config, get_config


def get_logger():
    logging.basicConfig(level=logging.INFO)
    return logging.getLogger()


logger = get_logger()


class NoArgumentProvided:
    """ "
    We use this class as a replacement for ``None`` as a default argument,
    to distinguish cases where the user doesn't provide an argument
    from cases where they intentionally provide ``None`` as an argument.
    """

    pass


def get_arg_from_dict(x, desired: str, use_default=False, default=None):
    if desired not in x:
        if use_default:
            return default
        else:
            raise KeyError
    return x[desired]


def sql_sample_one(x):
    from sqlalchemy.sql import func

    return x.order_by(func.random()).first()


def get_experiment():
    """
    Returns an initialized instance of the experiment class.
    """
    return import_local_experiment()["class"](db.session)


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


config_defaults = {
    "keep_old_chrome_windows_in_debug_mode": False,
}


def get_from_config(key):
    global config_defaults

    config = get_config()
    if not config.ready:
        config.load()

    if key in config_defaults:
        return config.get(key, default=config_defaults[key])
    else:
        return config.get(key)


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
    import pandas as pd

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
    import pandas as pd

    columns = []
    for row in json_data:
        [columns.append(key) for key in row.keys() if key not in columns]

    data_frame = pd.DataFrame.from_records(json_data, columns=columns)
    return data_frame


def wait_until(condition, max_wait, poll_interval=0.5, error_message=None):
    if condition():
        return True
    else:
        waited = 0.0
        while waited <= max_wait:
            time.sleep(poll_interval)
            waited += poll_interval
            if condition():
                return True
        if error_message is None:
            error_message = (
                "Condition was not satisfied within the required time interval."
            )
        raise RuntimeError(error_message)


def wait_while(condition, **kwargs):
    wait_until(lambda: not condition(), **kwargs)


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


def is_valid_html5_id(str):
    if not str or " " in str:
        return False
    return True


def pretty_format_seconds(seconds):
    minutes_and_seconds = divmod(seconds, 60)
    seconds_remainder = round(minutes_and_seconds[1])
    formatted_time = f"{round(minutes_and_seconds[0])} min"
    if seconds_remainder > 0:
        formatted_time += f" {seconds_remainder} sec"
    return formatted_time


def pretty_log_dict(dict, spaces_for_indentation=0):
    return "\n".join(
        " " * spaces_for_indentation
        + "{}: {}".format(key, (f'"{value}"' if isinstance(value, str) else value))
        for key, value in dict.items()
    )


def get_language():
    """
    Returns the language selected in config.txt.
    Throws a KeyError if no such language is specified.

    Returns
    -------

    A string, for example "en".
    """
    if not config.ready:
        config.load()
    return config.get("language")


def sample_from_surface_of_unit_sphere(n_dimensions):
    import numpy as np

    res = np.random.randn(n_dimensions, 1)
    res /= np.linalg.norm(res, axis=0)
    return res[:, 0].tolist()


def error_page(
    participant=None,
    error_text=None,
    compensate=True,
    error_type="default",
    request_data="",
):
    """Render HTML for error page."""
    from flask import make_response, render_template, request

    config = get_config()

    if error_text is None:
        error_text = "There has been an error and so you are unable to continue, sorry!"

    if participant is not None:
        hit_id = participant.hit_id
        assignment_id = participant.assignment_id
        worker_id = participant.worker_id
        participant_id = participant.id
    else:
        hit_id = request.form.get("hit_id", "")
        assignment_id = request.form.get("assignment_id", "")
        worker_id = request.form.get("worker_id", "")
        participant_id = request.form.get("participant_id", None)

    if participant_id:
        try:
            participant_id = int(participant_id)
        except (ValueError, TypeError):
            participant_id = None

    return make_response(
        render_template(
            "mturk_error.html",
            error_text=error_text,
            compensate=compensate,
            contact_address=config.get("contact_email_on_error"),
            error_type=error_type,
            hit_id=hit_id,
            assignment_id=assignment_id,
            worker_id=worker_id,
            request_data=request_data,
            participant_id=participant_id,
        ),
        500,
    )


class ClassPropertyDescriptor(object):
    def __init__(self, fget, fset=None):
        self.fget = fget
        self.fset = fset

    def __get__(self, obj, cls=None):
        if cls is None:
            cls = type(obj)
        return self.fget.__get__(obj, cls)()

    def __set__(self, obj, value):
        if not self.fset:
            raise AttributeError("can't set attribute")
        type_ = type(obj)
        return self.fset.__get__(obj, type_)(value)

    def setter(self, func):
        if not isinstance(func, (classmethod, staticmethod)):
            func = classmethod(func)
        self.fset = func
        return self


def classproperty(func):
    """
    Defines an analogous version of @property but for classes,
    after https://stackoverflow.com/questions/5189699/how-to-make-a-class-property.
    """
    if not isinstance(func, (classmethod, staticmethod)):
        func = classmethod(func)

    return ClassPropertyDescriptor(func)


def run_subprocess_with_live_output(command):
    p = pexpect.spawn(command, timeout=None)
    while not p.eof():
        line = p.readline().decode("utf-8")
        print(line, end="")
    p.close()
    if p.exitstatus > 0:
        sys.exit(p.exitstatus)


def organize_by_key(lst, key):
    """
    Sorts a list of items into groups.

    Parameters
    ----------
    lst :
        List to sort.

    key :
        Function applied to elements of ``lst`` which defines the grouping key.

    Returns
    -------

    A dictionary keyed by the outputs of ``key``.

    """
    out = {}
    for obj in lst:
        _key = key(obj)
        if _key not in out:
            out[_key] = []
        out[_key].append(obj)
    return out
