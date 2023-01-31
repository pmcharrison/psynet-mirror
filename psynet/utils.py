import base64
import contextlib
import gettext
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
from collections import OrderedDict
from datetime import datetime
from functools import lru_cache, reduce, wraps
from os.path import abspath, dirname, exists
from os.path import join as join_path
from pathlib import Path
from typing import Type, Union
from urllib.parse import ParseResult, urlparse

import jsonpickle
import pexpect
from _hashlib import HASH as Hash
from babel.support import Translations
from dallinger.config import config, get_config
from flask import url_for
from flask.globals import current_app, request
from flask.templating import Environment, _render


def get_logger():
    logging.basicConfig(level=logging.INFO)
    return logging.getLogger()


logger = get_logger()
DEFAULT_LOCALE = "en"


class NoArgumentProvided:
    """
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
    Calls a function with ``*args`` and ``**kwargs``, but omits any ``**kwargs`` that are
    not requested explicitly.
    """
    kwargs = {key: value for key, value in kwargs.items() if key in get_args(function)}
    return function(*args, **kwargs)


def call_function_with_context(function, *args, **kwargs):
    from psynet.trial.main import Trial

    participant = kwargs.get("participant", NoArgumentProvided)
    experiment = kwargs.get("experiment", NoArgumentProvided)
    assets = kwargs.get("assets", NoArgumentProvided)
    nodes = kwargs.get("nodes", NoArgumentProvided)
    trial_maker = kwargs.get("trial_maker", NoArgumentProvided)

    requested = get_args(function)

    if participant != NoArgumentProvided and participant.module_state:
        if "assets" in requested and assets == NoArgumentProvided:
            with time_logger("participant.module_state.assets"):
                assets = participant.module_state.assets

        if "nodes" in requested and nodes == NoArgumentProvided:
            with time_logger("participant.module_state.nodes"):
                nodes = participant.module_state.nodes

    if "trial_maker" in requested and trial_maker == NoArgumentProvided:
        if (
            participant != NoArgumentProvided
            and participant.in_module
            and isinstance(participant.current_trial, Trial)
        ):
            with time_logger("participant.current_trial.trial_maker"):
                trial_maker = participant.current_trial.trial_maker

    new_kwargs = {
        "experiment": experiment,
        "participant": participant,
        "assets": assets,
        "nodes": nodes,
        "trial_maker": trial_maker,
        **kwargs,
    }

    return call_function(function, *args, **new_kwargs)


config_defaults = {
    "keep_old_chrome_windows_in_debug_mode": False,
    "debug_storage_root": "~/psynet-data/debug",  # TODO - revisit whether this is ignored
    "default_export_root": "~/psynet-data/export",  # TODO - revisit whether this is ignored
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
        with time_logger(fun.__name__):
            res = fun(*args, **kwargs)
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
    """
    Ask a yes/no question via raw_input() and return their answer.

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
    if not Path(filename).is_file():
        raise FileNotFoundError(f"File not found: {filename}")
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
    return config.get("language", "en")


def _render_with_translations(
    locale, template_name=None, template_string=None, all_template_args=None
):
    """Render a template with translations applied."""

    if all_template_args is None:
        all_template_args = {}
    assert [template_name, template_string].count(
        None
    ) == 1, "Only one of template_name or template_string should be provided."

    app = current_app._get_current_object()  # type: ignore[attr-defined]
    gettext, pgettext, npgettext = get_translator(locale)
    gettext_functions = [gettext, pgettext, npgettext, url_for]
    gettext_abbr = {_f.__name__: _f for _f in gettext_functions}
    translation = Translations.load("translations", [locale])

    environment = Environment(
        loader=app.jinja_env.loader, extensions=["jinja2.ext.i18n"], app=app
    )
    environment.install_gettext_translations(translation)

    environment.globals.update(**gettext_abbr)

    if template_name is not None:
        template = environment.get_template(template_name)
    else:
        template = environment.from_string(template_string)
    return _render(app, template, all_template_args)


def render_template_with_translations(template_name, locale=None, **kwargs):
    return _render_with_translations(
        template_name=template_name, locale=locale, all_template_args=kwargs
    )


def render_string_with_translations(template_string, locale=None, **kwargs):
    return _render_with_translations(
        template_string=template_string, locale=locale, all_template_args=kwargs
    )


def get_translator(
    locale=None,
    module="psynet",
    localedir=join_path(abspath(dirname(__file__)), "locales"),
):
    if locale is None:
        try:
            GET = request.args.to_dict()
            possible_keys = ["assignmentId", "workerId", "participantId"]
            from psynet.participant import Participant

            if any([key in GET for key in possible_keys]):
                if "assignmentId" in GET:
                    participant = Participant.query.filter_by(
                        assignment_id=GET["assignment_id"]
                    ).one()
                elif "workerId" in GET:
                    participant = Participant.query.filter_by(
                        worker_id=int(GET["worker_id"])
                    ).one()
                elif "participantId" in GET:
                    participant = Participant.query.filter_by(
                        id=GET["participant_id"]
                    ).one()
                locale = participant.var.locale
        except Exception:
            pass
    if locale is None:
        locale = get_language()
    if exists(join_path(localedir, locale, "LC_MESSAGES", f"{module}.mo")):
        translator = gettext.translation(module, localedir, [locale])
    else:
        if locale != "en":
            logger.warning(f"No translation file found for locale {locale}.")
        translator = gettext.NullTranslations()

    return translator.gettext, translator.pgettext, translator.npgettext


def countries(locale=None):
    """
    List compiled using the pycountry package v20.7.3 with

    ::

        sorted([(lang.alpha_2, lang.name) for lang in pycountry.countries
            if hasattr(lang, 'alpha_2')], key=lambda country: country[1])
    """
    _, _p, _np = get_translator(locale)
    return [
        ("AF", _p("country_name", "Afghanistan")),
        ("AL", _p("country_name", "Albania")),
        ("DZ", _p("country_name", "Algeria")),
        ("AS", _p("country_name", "American Samoa")),
        ("AD", _p("country_name", "Andorra")),
        ("AO", _p("country_name", "Angola")),
        ("AI", _p("country_name", "Anguilla")),
        ("AQ", _p("country_name", "Antarctica")),
        ("AG", _p("country_name", "Antigua and Barbuda")),
        ("AR", _p("country_name", "Argentina")),
        ("AM", _p("country_name", "Armenia")),
        ("AW", _p("country_name", "Aruba")),
        ("AU", _p("country_name", "Australia")),
        ("AT", _p("country_name", "Austria")),
        ("AZ", _p("country_name", "Azerbaijan")),
        ("BS", _p("country_name", "Bahamas")),
        ("BH", _p("country_name", "Bahrain")),
        ("BD", _p("country_name", "Bangladesh")),
        ("BB", _p("country_name", "Barbados")),
        ("BY", _p("country_name", "Belarus")),
        ("BE", _p("country_name", "Belgium")),
        ("BZ", _p("country_name", "Belize")),
        ("BJ", _p("country_name", "Benin")),
        ("BM", _p("country_name", "Bermuda")),
        ("BT", _p("country_name", "Bhutan")),
        ("BO", _p("country_name", "Bolivia")),
        ("BQ", _p("country_name", "Bonaire, Sint Eustatius and Saba")),
        ("BA", _p("country_name", "Bosnia and Herzegovina")),
        ("BW", _p("country_name", "Botswana")),
        ("BV", _p("country_name", "Bouvet Island")),
        ("BR", _p("country_name", "Brazil")),
        ("IO", _p("country_name", "British Indian Ocean Territory")),
        ("BN", _p("country_name", "Brunei Darussalam")),
        ("BG", _p("country_name", "Bulgaria")),
        ("BF", _p("country_name", "Burkina Faso")),
        ("BI", _p("country_name", "Burundi")),
        ("CV", _p("country_name", "Cabo Verde")),
        ("KH", _p("country_name", "Cambodia")),
        ("CM", _p("country_name", "Cameroon")),
        ("CA", _p("country_name", "Canada")),
        ("KY", _p("country_name", "Cayman Islands")),
        ("CF", _p("country_name", "Central African Republic")),
        ("TD", _p("country_name", "Chad")),
        ("CL", _p("country_name", "Chile")),
        ("CN", _p("country_name", "China")),
        ("CX", _p("country_name", "Christmas Island")),
        ("CC", _p("country_name", "Cocos  Islands")),
        ("CO", _p("country_name", "Colombia")),
        ("KM", _p("country_name", "Comoros")),
        ("CG", _p("country_name", "Congo")),
        ("CD", _p("country_name", "Congo (Democratic Republic)")),
        ("CK", _p("country_name", "Cook Islands")),
        ("CR", _p("country_name", "Costa Rica")),
        ("HR", _p("country_name", "Croatia")),
        ("CU", _p("country_name", "Cuba")),
        ("CW", _p("country_name", "Curaçao")),
        ("CY", _p("country_name", "Cyprus")),
        ("CZ", _p("country_name", "Czechia")),
        ("CI", _p("country_name", "Côte d'Ivoire")),
        ("DK", _p("country_name", "Denmark")),
        ("DJ", _p("country_name", "Djibouti")),
        ("DM", _p("country_name", "Dominica")),
        ("DO", _p("country_name", "Dominican Republic")),
        ("EC", _p("country_name", "Ecuador")),
        ("EG", _p("country_name", "Egypt")),
        ("SV", _p("country_name", "El Salvador")),
        ("GQ", _p("country_name", "Equatorial Guinea")),
        ("ER", _p("country_name", "Eritrea")),
        ("EE", _p("country_name", "Estonia")),
        ("SZ", _p("country_name", "Eswatini")),
        ("ET", _p("country_name", "Ethiopia")),
        ("FK", _p("country_name", "Falkland Islands (Malvinas)")),
        ("FO", _p("country_name", "Faroe Islands")),
        ("FJ", _p("country_name", "Fiji")),
        ("FI", _p("country_name", "Finland")),
        ("FR", _p("country_name", "France")),
        ("GF", _p("country_name", "French Guiana")),
        ("PF", _p("country_name", "French Polynesia")),
        ("TF", _p("country_name", "French Southern Territories")),
        ("GA", _p("country_name", "Gabon")),
        ("GM", _p("country_name", "Gambia")),
        ("GE", _p("country_name", "Georgia")),
        ("DE", _p("country_name", "Germany")),
        ("GH", _p("country_name", "Ghana")),
        ("GI", _p("country_name", "Gibraltar")),
        ("GR", _p("country_name", "Greece")),
        ("GL", _p("country_name", "Greenland")),
        ("GD", _p("country_name", "Grenada")),
        ("GP", _p("country_name", "Guadeloupe")),
        ("GU", _p("country_name", "Guam")),
        ("GT", _p("country_name", "Guatemala")),
        ("GG", _p("country_name", "Guernsey")),
        ("GN", _p("country_name", "Guinea")),
        ("GW", _p("country_name", "Guinea-Bissau")),
        ("GY", _p("country_name", "Guyana")),
        ("HT", _p("country_name", "Haiti")),
        ("HM", _p("country_name", "Heard Island and McDonald Islands")),
        ("VA", _p("country_name", "Vatican City State")),
        ("HN", _p("country_name", "Honduras")),
        ("HK", _p("country_name", "Hong Kong")),
        ("HU", _p("country_name", "Hungary")),
        ("IS", _p("country_name", "Iceland")),
        ("IN", _p("country_name", "India")),
        ("ID", _p("country_name", "Indonesia")),
        ("IR", _p("country_name", "Iran")),
        ("IQ", _p("country_name", "Iraq")),
        ("IE", _p("country_name", "Ireland")),
        ("IM", _p("country_name", "Isle of Man")),
        ("IL", _p("country_name", "Israel")),
        ("IT", _p("country_name", "Italy")),
        ("JM", _p("country_name", "Jamaica")),
        ("JP", _p("country_name", "Japan")),
        ("JE", _p("country_name", "Jersey")),
        ("JO", _p("country_name", "Jordan")),
        ("KZ", _p("country_name", "Kazakhstan")),
        ("KE", _p("country_name", "Kenya")),
        ("KI", _p("country_name", "Kiribati")),
        ("KP", _p("country_name", "North Korea")),
        ("KR", _p("country_name", "South Korea")),
        ("KW", _p("country_name", "Kuwait")),
        ("KG", _p("country_name", "Kyrgyzstan")),
        ("LA", _p("country_name", "Lao")),
        ("LV", _p("country_name", "Latvia")),
        ("LB", _p("country_name", "Lebanon")),
        ("LS", _p("country_name", "Lesotho")),
        ("LR", _p("country_name", "Liberia")),
        ("LY", _p("country_name", "Libya")),
        ("LI", _p("country_name", "Liechtenstein")),
        ("LT", _p("country_name", "Lithuania")),
        ("LU", _p("country_name", "Luxembourg")),
        ("MO", _p("country_name", "Macao")),
        ("MG", _p("country_name", "Madagascar")),
        ("MW", _p("country_name", "Malawi")),
        ("MY", _p("country_name", "Malaysia")),
        ("MV", _p("country_name", "Maldives")),
        ("ML", _p("country_name", "Mali")),
        ("MT", _p("country_name", "Malta")),
        ("MH", _p("country_name", "Marshall Islands")),
        ("MQ", _p("country_name", "Martinique")),
        ("MR", _p("country_name", "Mauritania")),
        ("MU", _p("country_name", "Mauritius")),
        ("YT", _p("country_name", "Mayotte")),
        ("MX", _p("country_name", "Mexico")),
        ("FM", _p("country_name", "Micronesia")),
        ("MD", _p("country_name", "Moldova")),
        ("MC", _p("country_name", "Monaco")),
        ("MN", _p("country_name", "Mongolia")),
        ("ME", _p("country_name", "Montenegro")),
        ("MS", _p("country_name", "Montserrat")),
        ("MA", _p("country_name", "Morocco")),
        ("MZ", _p("country_name", "Mozambique")),
        ("MM", _p("country_name", "Myanmar")),
        ("NA", _p("country_name", "Namibia")),
        ("NR", _p("country_name", "Nauru")),
        ("NP", _p("country_name", "Nepal")),
        ("NL", _p("country_name", "Netherlands")),
        ("NC", _p("country_name", "New Caledonia")),
        ("NZ", _p("country_name", "New Zealand")),
        ("NI", _p("country_name", "Nicaragua")),
        ("NE", _p("country_name", "Niger")),
        ("NG", _p("country_name", "Nigeria")),
        ("NU", _p("country_name", "Niue")),
        ("NF", _p("country_name", "Norfolk Island")),
        ("MK", _p("country_name", "North Macedonia")),
        ("MP", _p("country_name", "Northern Mariana Islands")),
        ("NO", _p("country_name", "Norway")),
        ("OM", _p("country_name", "Oman")),
        ("PK", _p("country_name", "Pakistan")),
        ("PW", _p("country_name", "Palau")),
        ("PS", _p("country_name", "Palestine")),
        ("PA", _p("country_name", "Panama")),
        ("PG", _p("country_name", "Papua New Guinea")),
        ("PY", _p("country_name", "Paraguay")),
        ("PE", _p("country_name", "Peru")),
        ("PH", _p("country_name", "Philippines")),
        ("PN", _p("country_name", "Pitcairn")),
        ("PL", _p("country_name", "Poland")),
        ("PT", _p("country_name", "Portugal")),
        ("PR", _p("country_name", "Puerto Rico")),
        ("QA", _p("country_name", "Qatar")),
        ("RO", _p("country_name", "Romania")),
        ("RU", _p("country_name", "Russian Federation")),
        ("RW", _p("country_name", "Rwanda")),
        ("RE", _p("country_name", "Réunion")),
        ("BL", _p("country_name", "Saint Barthélemy")),
        ("SH", _p("country_name", "Saint Helena, Ascension and Tristan da Cunha")),
        ("KN", _p("country_name", "Saint Kitts and Nevis")),
        ("LC", _p("country_name", "Saint Lucia")),
        ("MF", _p("country_name", "Saint Martin")),
        ("PM", _p("country_name", "Saint Pierre and Miquelon")),
        ("VC", _p("country_name", "Saint Vincent and the Grenadines")),
        ("WS", _p("country_name", "Samoa")),
        ("SM", _p("country_name", "San Marino")),
        ("ST", _p("country_name", "Sao Tome and Principe")),
        ("SA", _p("country_name", "Saudi Arabia")),
        ("SN", _p("country_name", "Senegal")),
        ("RS", _p("country_name", "Serbia")),
        ("SC", _p("country_name", "Seychelles")),
        ("SL", _p("country_name", "Sierra Leone")),
        ("SG", _p("country_name", "Singapore")),
        ("SX", _p("country_name", "Sint Maarten")),
        ("SK", _p("country_name", "Slovakia")),
        ("SI", _p("country_name", "Slovenia")),
        ("SB", _p("country_name", "Solomon Islands")),
        ("SO", _p("country_name", "Somalia")),
        ("ZA", _p("country_name", "South Africa")),
        ("GS", _p("country_name", "South Georgia and the South Sandwich Islands")),
        ("SS", _p("country_name", "South Sudan")),
        ("ES", _p("country_name", "Spain")),
        ("LK", _p("country_name", "Sri Lanka")),
        ("SD", _p("country_name", "Sudan")),
        ("SR", _p("country_name", "Suriname")),
        ("SJ", _p("country_name", "Svalbard and Jan Mayen")),
        ("SE", _p("country_name", "Sweden")),
        ("CH", _p("country_name", "Switzerland")),
        ("SY", _p("country_name", "Syria")),
        ("TW", _p("country_name", "Taiwan")),
        ("TJ", _p("country_name", "Tajikistan")),
        ("TZ", _p("country_name", "Tanzania")),
        ("TH", _p("country_name", "Thailand")),
        ("TL", _p("country_name", "Timor-Leste")),
        ("TG", _p("country_name", "Togo")),
        ("TK", _p("country_name", "Tokelau")),
        ("TO", _p("country_name", "Tonga")),
        ("TT", _p("country_name", "Trinidad and Tobago")),
        ("TN", _p("country_name", "Tunisia")),
        ("TR", _p("country_name", "Turkey")),
        ("TM", _p("country_name", "Turkmenistan")),
        ("TC", _p("country_name", "Turks and Caicos Islands")),
        ("TV", _p("country_name", "Tuvalu")),
        ("UG", _p("country_name", "Uganda")),
        ("UA", _p("country_name", "Ukraine")),
        ("AE", _p("country_name", "United Arab Emirates")),
        ("GB", _p("country_name", "United Kingdom")),
        ("US", _p("country_name", "United States")),
        ("UM", _p("country_name", "United States Minor Outlying Islands")),
        ("UY", _p("country_name", "Uruguay")),
        ("UZ", _p("country_name", "Uzbekistan")),
        ("VU", _p("country_name", "Vanuatu")),
        ("VE", _p("country_name", "Venezuela")),
        ("VN", _p("country_name", "Vietnam")),
        ("VG", _p("country_name", "Virgin Islands (British)")),
        ("VI", _p("country_name", "Virgin Islands (U.S.)")),
        ("WF", _p("country_name", "Wallis and Futuna")),
        ("EH", _p("country_name", "Western Sahara")),
        ("YE", _p("country_name", "Yemen")),
        ("ZM", _p("country_name", "Zambia")),
        ("ZW", _p("country_name", "Zimbabwe")),
        ("AX", _p("country_name", "Åland Islands")),
    ]


def languages(locale=None):
    """
    List compiled using the pycountry package v20.7.3 with

    ::

        sorted([(lang.alpha_2, lang.name) for lang in pycountry.languages
            if hasattr(lang, 'alpha_2')], key=lambda country: country[1])
    """
    _, _p, _np = get_translator(locale)
    return [
        ("ab", _p("language_name", "Abkhazian")),
        ("aa", _p("language_name", "Afar")),
        ("af", _p("language_name", "Afrikaans")),
        ("ak", _p("language_name", "Akan")),
        ("sq", _p("language_name", "Albanian")),
        ("am", _p("language_name", "Amharic")),
        ("ar", _p("language_name", "Arabic")),
        ("an", _p("language_name", "Aragonese")),
        ("hy", _p("language_name", "Armenian")),
        ("as", _p("language_name", "Assamese")),
        ("av", _p("language_name", "Avaric")),
        ("ae", _p("language_name", "Avestan")),
        ("ay", _p("language_name", "Aymara")),
        ("az", _p("language_name", "Azerbaijani")),
        ("bm", _p("language_name", "Bambara")),
        ("ba", _p("language_name", "Bashkir")),
        ("eu", _p("language_name", "Basque")),
        ("be", _p("language_name", "Belarusian")),
        ("bn", _p("language_name", "Bengali")),
        ("bi", _p("language_name", "Bislama")),
        ("bs", _p("language_name", "Bosnian")),
        ("br", _p("language_name", "Breton")),
        ("bg", _p("language_name", "Bulgarian")),
        ("my", _p("language_name", "Burmese")),
        ("ca", _p("language_name", "Catalan")),
        ("km", _p("language_name", "Central Khmer")),
        ("ch", _p("language_name", "Chamorro")),
        ("ce", _p("language_name", "Chechen")),
        ("zh", _p("language_name", "Chinese")),
        ("zh-cn", _p("language_name", "Chinese")),
        ("cu", _p("language_name", "Church Slavic")),
        ("cv", _p("language_name", "Chuvash")),
        ("kw", _p("language_name", "Cornish")),
        ("co", _p("language_name", "Corsican")),
        ("cr", _p("language_name", "Cree")),
        ("hr", _p("language_name", "Croatian")),
        ("ceb", _p("language_name", "Cebuano")),
        ("cs", _p("language_name", "Czech")),
        ("da", _p("language_name", "Danish")),
        ("dv", _p("language_name", "Dhivehi")),
        ("nl", _p("language_name", "Dutch")),
        ("dz", _p("language_name", "Dzongkha")),
        ("en", _p("language_name", "English")),
        ("eo", _p("language_name", "Esperanto")),
        ("et", _p("language_name", "Estonian")),
        ("ee", _p("language_name", "Ewe")),
        ("fo", _p("language_name", "Faroese")),
        ("fj", _p("language_name", "Fijian")),
        ("fi", _p("language_name", "Finnish")),
        ("fr", _p("language_name", "French")),
        ("ff", _p("language_name", "Fulah")),
        ("gl", _p("language_name", "Galician")),
        ("lg", _p("language_name", "Ganda")),
        ("ka", _p("language_name", "Georgian")),
        ("de", _p("language_name", "German")),
        ("got", _p("language_name", "Gothic")),
        ("gn", _p("language_name", "Guarani")),
        ("gu", _p("language_name", "Gujarati")),
        ("ht", _p("language_name", "Haitian")),
        ("ha", _p("language_name", "Hausa")),
        ("haw", _p("language_name", "Hawaiian")),
        ("he", _p("language_name", "Hebrew")),
        ("hz", _p("language_name", "Herero")),
        ("hi", _p("language_name", "Hindi")),
        ("ho", _p("language_name", "Hiri Motu")),
        ("hmn", _p("language_name", "Hmong")),
        ("hu", _p("language_name", "Hungarian")),
        ("is", _p("language_name", "Icelandic")),
        ("io", _p("language_name", "Ido")),
        ("ig", _p("language_name", "Igbo")),
        ("id", _p("language_name", "Indonesian")),
        ("ia", _p("language_name", "Interlingua")),
        ("ie", _p("language_name", "Interlingue")),
        ("iu", _p("language_name", "Inuktitut")),
        ("ik", _p("language_name", "Inupiaq")),
        ("ga", _p("language_name", "Irish")),
        ("it", _p("language_name", "Italian")),
        ("ja", _p("language_name", "Japanese")),
        ("jv", _p("language_name", "Javanese")),
        ("jw", _p("language_name", "Javanese")),
        ("kl", _p("language_name", "Kalaallisut")),
        ("kn", _p("language_name", "Kannada")),
        ("kr", _p("language_name", "Kanuri")),
        ("ks", _p("language_name", "Kashmiri")),
        ("kk", _p("language_name", "Kazakh")),
        ("ki", _p("language_name", "Kikuyu")),
        ("rw", _p("language_name", "Kinyarwanda")),
        ("ky", _p("language_name", "Kirghiz")),
        ("kv", _p("language_name", "Komi")),
        ("kg", _p("language_name", "Kongo")),
        ("ko", _p("language_name", "Korean")),
        ("kj", _p("language_name", "Kuanyama")),
        ("ku", _p("language_name", "Kurdish")),
        ("lo", _p("language_name", "Lao")),
        ("la", _p("language_name", "Latin")),
        ("lv", _p("language_name", "Latvian")),
        ("li", _p("language_name", "Limburgan")),
        ("ln", _p("language_name", "Lingala")),
        ("lt", _p("language_name", "Lithuanian")),
        ("lu", _p("language_name", "Luba-Katanga")),
        ("lb", _p("language_name", "Luxembourgish")),
        ("mk", _p("language_name", "Macedonian")),
        ("mg", _p("language_name", "Malagasy")),
        ("ms", _p("language_name", "Malay")),
        ("ml", _p("language_name", "Malayalam")),
        ("mt", _p("language_name", "Maltese")),
        ("gv", _p("language_name", "Manx")),
        ("mi", _p("language_name", "Maori")),
        ("mr", _p("language_name", "Marathi")),
        ("mh", _p("language_name", "Marshallese")),
        ("el", _p("language_name", "Greek")),
        ("mn", _p("language_name", "Mongolian")),
        ("na", _p("language_name", "Nauru")),
        ("nv", _p("language_name", "Navajo")),
        ("ng", _p("language_name", "Ndonga")),
        ("ne", _p("language_name", "Nepali")),
        ("nd", _p("language_name", "North Ndebele")),
        ("se", _p("language_name", "Northern Sami")),
        ("no", _p("language_name", "Norwegian")),
        ("nb", _p("language_name", "Norwegian Bokmål")),
        ("nn", _p("language_name", "Norwegian Nynorsk")),
        ("ny", _p("language_name", "Nyanja")),
        ("oc", _p("language_name", "Occitan")),
        ("oj", _p("language_name", "Ojibwa")),
        ("or", _p("language_name", "Oriya")),
        ("om", _p("language_name", "Oromo")),
        ("os", _p("language_name", "Ossetian")),
        ("pi", _p("language_name", "Pali")),
        ("pa", _p("language_name", "Panjabi")),
        ("fa", _p("language_name", "Persian")),
        ("pl", _p("language_name", "Polish")),
        ("pt", _p("language_name", "Portuguese")),
        ("ps", _p("language_name", "Pushto")),
        ("qu", _p("language_name", "Quechua")),
        ("ro", _p("language_name", "Romanian")),
        ("rm", _p("language_name", "Romansh")),
        ("rn", _p("language_name", "Rundi")),
        ("ru", _p("language_name", "Russian")),
        ("sm", _p("language_name", "Samoan")),
        ("sg", _p("language_name", "Sango")),
        ("sa", _p("language_name", "Sanskrit")),
        ("sc", _p("language_name", "Sardinian")),
        ("gd", _p("language_name", "Scottish Gaelic")),
        ("sr", _p("language_name", "Serbian")),
        ("sh", _p("language_name", "Serbo-Croatian")),
        ("sn", _p("language_name", "Shona")),
        ("ii", _p("language_name", "Sichuan Yi")),
        ("sd", _p("language_name", "Sindhi")),
        ("si", _p("language_name", "Sinhala")),
        ("sk", _p("language_name", "Slovak")),
        ("sl", _p("language_name", "Slovenian")),
        ("so", _p("language_name", "Somali")),
        ("nr", _p("language_name", "South Ndebele")),
        ("st", _p("language_name", "Southern Sotho")),
        ("es", _p("language_name", "Spanish")),
        ("su", _p("language_name", "Sundanese")),
        ("sw", _p("language_name", "Swahili")),
        ("ss", _p("language_name", "Swati")),
        ("sv", _p("language_name", "Swedish")),
        ("zh-tw", _p("language_name", "Taiwanese")),
        ("tl", _p("language_name", "Tagalog")),
        ("ty", _p("language_name", "Tahitian")),
        ("tg", _p("language_name", "Tajik")),
        ("ta", _p("language_name", "Tamil")),
        ("tt", _p("language_name", "Tatar")),
        ("te", _p("language_name", "Telugu")),
        ("th", _p("language_name", "Thai")),
        ("bo", _p("language_name", "Tibetan")),
        ("ti", _p("language_name", "Tigrinya")),
        ("to", _p("language_name", "Tonga")),
        ("ts", _p("language_name", "Tsonga")),
        ("tn", _p("language_name", "Tswana")),
        ("tr", _p("language_name", "Turkish")),
        ("tk", _p("language_name", "Turkmen")),
        ("tw", _p("language_name", "Twi")),
        ("ug", _p("language_name", "Uighur")),
        ("uk", _p("language_name", "Ukrainian")),
        ("ur", _p("language_name", "Urdu")),
        ("uz", _p("language_name", "Uzbek")),
        ("ve", _p("language_name", "Venda")),
        ("vi", _p("language_name", "Vietnamese")),
        ("vo", _p("language_name", "Volapük")),
        ("wa", _p("language_name", "Walloon")),
        ("cy", _p("language_name", "Welsh")),
        ("hyw", _p("language_name", "Western Armenian")),
        ("fy", _p("language_name", "Western Frisian")),
        ("wo", _p("language_name", "Wolof")),
        ("xh", _p("language_name", "Xhosa")),
        ("yi", _p("language_name", "Yiddish")),
        ("yo", _p("language_name", "Yoruba")),
        ("za", _p("language_name", "Zhuang")),
        ("zu", _p("language_name", "Zulu")),
    ]


def _get_entity_dict_from_tuple_list(tuple_list, sort_by_value):
    dictionary = dict(
        zip([key for key, value in tuple_list], [value for key, value in tuple_list])
    )
    if sort_by_value:
        return dict(OrderedDict(sorted(dictionary.items(), key=lambda t: t[1])))
    else:
        return dictionary


def get_language_dict(locale, sort_by_name=True):
    return _get_entity_dict_from_tuple_list(languages(locale), sort_by_name)


def get_country_dict(locale, sort_by_name=True):
    return _get_entity_dict_from_tuple_list(countries(locale), sort_by_name)


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
    locale=DEFAULT_LOCALE,
):
    """Render HTML for error page."""
    from flask import make_response, request

    config = get_config()
    _, _p, _np = get_translator(locale)
    if error_text is None:
        error_text = _p(
            "error-msg",
            "There has been an error and so you are unable to continue, sorry!",
        )

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
        render_template_with_translations(
            "mturk_error.html",
            locale=locale,
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


def organize_by_key(lst, key, sort_key=None):
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
    if sort_key:
        for value in out.values():
            value.sort(key=sort_key)
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

    for obj in gc.get_objects():
        try:
            if isinstance(obj, functools._lru_cache_wrapper):
                obj.cache_clear()
        except ReferenceError:
            pass


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


def is_method_overridden(obj, ancestor: Type, method: str):
    """
    Test whether a method has been overridden.

    Parameters
    ----------
    obj :
        Object to test.

    ancestor :
        Ancestor class to test against.

    method :
        Method name.

    Returns
    -------

    Returns ``True`` if the object shares a method with its ancestor,
    or ``False`` if that method has been overridden.

    """
    return getattr(obj.__class__, method) != getattr(ancestor, method)


time_logger_stack = []


@contextlib.contextmanager
def time_logger(label, threshold=0.01, indent=0.05):
    indent = len(time_logger_stack) * 4
    time_logger_stack.append(label)
    log = {
        "time_started": time.monotonic(),
        "time_finished": None,
        "time_taken": None,
    }
    if threshold == 0:
        logger.debug(
            "%s<-- START:                %s -->",
            " " * indent,
            label,
        )
    yield log
    log["time_finished"] = time.monotonic()
    log["time_taken"] = log["time_finished"] - log["time_started"]
    if log["time_taken"] > threshold:
        # stack = " stack-> ".join(time_logger_stack)
        # if isinstance(time_logger_stack[-1], CodeBlock):
        #     stack = stack + " " + inspect.getsource(time_logger_stack[-1].function)
        logger.debug(
            # "%.3f s: %s", log["time_taken"], stack
            "%s<-- FINISH after %.3f s: %s -->",
            " " * indent,
            log["time_taken"],
            label,
        ),  # log["time_taken"], label)
    time_logger_stack.pop()


@contextlib.contextmanager
def log_level(logger: logging.Logger, level):
    original_level = logger.level
    logger.setLevel(level)
    yield
    logger.setLevel(original_level)
