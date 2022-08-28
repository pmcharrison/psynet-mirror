import base64
import contextlib
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
from functools import lru_cache, reduce, wraps
from pathlib import Path
from typing import Union
from urllib.parse import ParseResult, urlparse

import jsonpickle
import pexpect
from _hashlib import HASH as Hash
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


def deep_copy(x):
    try:
        return jsonpickle.decode(jsonpickle.encode(x))
    except Exception:
        logger.error(f"Failed to copy the following object: {x}")
        raise


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


def dict_to_js_vars(x):
    y = [f"var {key} = JSON.parse('{json.dumps(value)}'); " for key, value in x.items()]
    return reduce(lambda a, b: a + b, y)


def call_function(function, *args, **kwargs):
    """
    Calls a function with *args and **kwargs, but omits any **kwargs that are
    not requested explicitly.
    """
    kwargs = {key: value for key, value in kwargs.items() if key in get_args(function)}
    return function(*args, **kwargs)


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


def get_args(f):
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


def md5_object(x):
    string = jsonpickle.encode(x).encode("utf-8")
    hashed = hashlib.md5(string)
    return str(hashed.hexdigest())


hash_object = md5_object


# MD5 hashing code:
# https://stackoverflow.com/a/54477583/8454486
def md5_update_from_file(filename: Union[str, Path], hash: Hash) -> Hash:
    assert Path(filename).is_file()
    with open(str(filename), "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash.update(chunk)
    return hash


def md5_file(filename: Union[str, Path]) -> str:
    return str(md5_update_from_file(filename, hashlib.md5()).hexdigest())


def md5_update_from_dir(directory: Union[str, Path], hash: Hash) -> Hash:
    assert Path(directory).is_dir()
    for path in sorted(Path(directory).iterdir(), key=lambda p: str(p).lower()):
        hash.update(path.name.encode())
        if path.is_file():
            hash = md5_update_from_file(path, hash)
        elif path.is_dir():
            hash = md5_update_from_dir(path, hash)
    return hash


def md5_directory(directory: Union[str, Path]) -> str:
    return str(md5_update_from_dir(directory, hashlib.md5()).hexdigest())


def format_hash(hashed, digits=32):
    return base64.urlsafe_b64encode(hashed.digest())[:digits].decode("utf-8")


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


def wait_until(
    condition, max_wait, poll_interval=0.5, error_message=None, *args, **kwargs
):
    if condition(*args, **kwargs):
        return True
    else:
        waited = 0.0
        while waited <= max_wait:
            time.sleep(poll_interval)
            waited += poll_interval
            if condition(*args, **kwargs):
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


def run_subprocess_with_live_output(command, timeout=None, cwd=None):
    _command = command.replace('"', '\\"').replace("'", "\\'")
    p = pexpect.spawn(f'bash -c "{_command}"', timeout=timeout, cwd=cwd)
    while not p.eof():
        line = p.readline().decode("utf-8")
        print(line, end="")
    p.close()
    if p.exitstatus > 0:
        sys.exit(p.exitstatus)


def get_extension(path):
    if path:
        _, extension = os.path.splitext(path)
        return extension
    else:
        return ""


# Backported from Python 3.9
def cache(user_function, /):
    'Simple lightweight unbounded cache.  Sometimes called "memoize".'
    return lru_cache(maxsize=None)(user_function)


def cached_class_property(f):
    return classmethod(property(cache(f)))


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


@contextlib.contextmanager
def working_directory(path):
    start_dir = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(start_dir)


def get_custom_sql_classes():
    """

    Returns
    -------

    A dictionary of all custom SQLAlchemy classes defined in the local experiment
    (excluding any which are defined within packages).
    """

    def f():
        return {
            cls.__name__: cls
            for _, module in inspect.getmembers(sys.modules["dallinger_experiment"])
            for _, cls in inspect.getmembers(module)
            if inspect.isclass(cls)
            and cls.__module__.startswith("dallinger_experiment")
            and hasattr(cls, "_sa_registry")
        }

    try:
        return f()
    except KeyError:
        import_local_experiment()
        return f()


def make_parents(path):
    """
    Creates the parent directories for a specified file if they don't exist already.

    Returns
    -------

    The original path.
    """
    Path(os.path.dirname(path)).mkdir(parents=True, exist_ok=True)
    return path


def bytes_to_megabytes(bytes):
    return bytes / (1024 * 1024)


def get_file_size_mb(path):
    bytes = os.path.getsize(path)
    return bytes_to_megabytes(bytes)


def get_folder_size_mb(path):
    bytes = sum(entry.stat().st_size for entry in os.scandir(path))
    return bytes_to_megabytes(bytes)


# def run_async_command_locally(fun, *args, **kwargs):
#     """
#     This is for when want to run a command asynchronously (so that it doesn't block current execution)
#     but locally (so that we know we have access to local files).
#     """
#
#     def wrapper():
#         f = io.StringIO()
#         with contextlib.redirect_stdout(f):
#             try:
#                 fun(*args, **kwargs)
#             except Exception:
#                 print(traceback.format_exc())
#         log_to_redis(f.getvalue())
#
#     import threading
#
#     thr = threading.Thread(target=wrapper)
#     thr.start()


# def log_to_redis(msg):
#     """
#     This passes the message to the Redis queue to be printed by the worker that picks it up.
#     This is useful for logging from processes that don't have access to the main logger.
#     """
#     q = Queue("default", connection=redis_conn)
#     q.enqueue_call(
#         func=logger.info, args=(), kwargs=dict(msg=msg), timeout=1e10, at_front=True
#     )


@contextlib.contextmanager
def disable_logger():
    logging.disable(sys.maxsize)
    yield
    logging.disable(logging.NOTSET)


def import_local_experiment():
    raise ImportError(
        "import_local_experiment has moved from psynet.utils to psynet.experiment, please update your import statements."
    )


def get_experiment():
    raise ImportError(
        "get_experiment has moved from psynet.utils to psynet.experiment, please update your import statements."
    )


def clear_all_caches():
    import functools
    import gc

    cached_functions = [
        i for i in gc.get_objects() if isinstance(i, functools._lru_cache_wrapper)
    ]

    for func in cached_functions:
        func.cache_clear()


@contextlib.contextmanager
def log_pexpect_errors(process):
    try:
        yield
    except (pexpect.EOF, pexpect.TIMEOUT) as err:
        print(f"A {err} error occurred. Printing process logs:")
        print(process.before)
        raise


# This seemed like a good idea for preventing cases where people use random functions
# in code blocks, page makers, etc. In practice however it didn't work, because
# some library functions tamper with the random state in a hidden way,
# making the check have too many false positives.
#
# @contextlib.contextmanager
# def disallow_random_functions(func_name, func=None):
#     random_state = random.getstate
#     numpy_random_state = numpy.random.get_state()
#
#     yield
#
#     if (
#         random.getstate() != random_state
#         or numpy.random.get_state() != numpy_random_state
#     ):
#         message = (
#             "It looks like you used Python's random number generator within "
#             f"your {func_name} code. This is disallowed because it allows your "
#             "experiment to get into inconsistent states. Instead you should generate "
#             "call any random number generators within code blocks, for_loop() constructs, "
#             "Trial.make_definition methods, or similar."
#         )
#         if func:
#             message += "\n"
#             message += "Offending code:\n"
#             message += inspect.getsource(func)
#
#         raise RuntimeError(message)
