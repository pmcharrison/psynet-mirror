import configparser
import json
import os
import re
import shutil
import sys
import tempfile
import time
import traceback
import uuid
import warnings
from collections import OrderedDict
from datetime import datetime
from importlib import resources
from os.path import abspath, dirname, exists
from os.path import join as join_path
from pathlib import Path
from platform import python_version
from smtplib import SMTPAuthenticationError
from statistics import mean
from typing import List

import dallinger.experiment
import dallinger.models
import flask
import pandas as pd
import pexpect
import psutil
import rpdb
import sqlalchemy.orm.exc
from click import Context
from dallinger import db
from dallinger.compat import unicode
from dallinger.config import get_config as dallinger_get_config
from dallinger.config import is_valid_json
from dallinger.experiment import experiment_route, scheduled_task
from dallinger.experiment_server.dashboard import dashboard_tab
from dallinger.experiment_server.utils import nocache, success_response
from dallinger.notifications import admin_notifier
from dallinger.recruiters import MTurkRecruiter, ProlificRecruiter, RecruitmentStatus
from dallinger.utils import get_base_url
from dallinger.version import __version__ as dallinger_version
from dominate import tags
from flask import g as flask_app_globals
from flask import jsonify, render_template, request, send_file
from sqlalchemy import Column, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import joinedload, relationship, with_polymorphic

from psynet import __version__
from psynet.utils import get_config

from . import deployment_info
from .asset import Asset, AssetRegistry, LocalStorage, OnDemandAsset
from .bot import Bot
from .command_line import export_launch_data, log
from .data import SQLBase, SQLMixin, ingest_zip, register_table
from .db import with_transaction
from .end import RejectedConsentLogic, SuccessfulEndLogic, UnsuccessfulEndLogic
from .error import ErrorRecord
from .field import ImmutableVarStore, PythonDict
from .graphics import PsyNetLogo
from .page import InfoPage
from .participant import Participant
from .recruiters import (  # noqa: F401
    BaseLucidRecruiter,
    CapRecruiter,
    DevCapRecruiter,
    DevLucidRecruiter,
    LucidRecruiter,
    StagingCapRecruiter,
)
from .redis import redis_vars
from .serialize import serialize
from .timeline import (
    DatabaseCheck,
    FailedValidation,
    ModuleState,
    ParticipantFailRoutine,
    PreDeployRoutine,
    RecruitmentCriterion,
    Response,
    Timeline,
)
from .translation.check import check_translations
from .translation.translate import create_pot
from .translation.utils import compile_mo, load_po
from .trial.main import Trial, TrialMaker
from .trial.record import (  # noqa -- this is to make sure the SQLAlchemy class is registered
    Recording,
)
from .utils import (
    NoArgumentProvided,
    cache,
    call_function,
    call_function_with_context,
    classproperty,
    disable_logger,
    get_arg_from_dict,
    get_logger,
    get_translator,
    log_time_taken,
    pretty_log_dict,
    render_template_with_translations,
    serialise,
    working_directory,
)

logger = get_logger()

database_template_path = ".deploy/database_template.zip"


DEFAULT_LOCALE = "en"
INITIAL_RECRUITMENT_SIZE = 1


def error_response(*args, **kwargs):
    from dallinger.experiment_server.utils import (
        error_response as dallinger_error_response,
    )

    with disable_logger():
        return dallinger_error_response(*args, **kwargs)


def is_experiment_launched():
    return redis_vars.get("launch_finished", default=False)


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime):
        serial = obj.isoformat()
        return serial
    raise TypeError("Type not serializable")


class ExperimentMeta(type):
    def __init__(cls, name, bases, dct):
        cls.assets = AssetRegistry(storage=cls.asset_storage)

        # This allows users to perform in-place alterations to ``css`` and ``css_links`` without
        # inadvertently altering the base class.
        cls.css = cls.css.copy()
        cls.css_links = cls.css_links.copy()

        if hasattr(cls, "test_create_bots"):
            raise RuntimeError(
                "Experiment.test_create_bots has been removed, please do not override it. Instead you should put "
                "any custom bot initialization code inside test_run_bot (before calling super().test_run_bot())."
            )

        if hasattr(cls, "test_run_bots"):
            raise RuntimeError(
                "Experiment.test_run_bots has been renamed to Experiment.test_serial_run_bots. "
                "Please note that this test route is only used if the tests are run in serial mode."
            )


@register_table
class Request(SQLBase, SQLMixin):
    __tablename__ = "request"

    # These fields are removed from the database table as they are not needed.
    failed = None
    failed_reason = None
    time_of_death = None
    vars = None

    id = Column(Integer, primary_key=True)
    unique_id = Column(String, ForeignKey("participant.unique_id"))
    duration = Column(Float)
    method = Column(String)
    endpoint = Column(String)
    params = Column(PythonDict, default={})

    def to_dict(self):
        return {
            "id": self.id,
            "duration": self.duration,
            "time": self.creation_time,
            "unique_id": self.unique_id,
            "method": self.method,
            "endpoint": self.endpoint,
            "params": self.params,
        }


@register_table
class ExperimentStatus(SQLBase, SQLMixin):
    __tablename__ = "experiment_status"

    id = Column(Integer, primary_key=True)
    cpu_usage_pct = Column(Float)
    ram_usage_pct = Column(Float)
    free_disk_space_gb = Column(Float)
    median_response_time = Column(Float)
    requests_per_minute = Column(Integer)
    n_working_participants = Column(Integer)
    extra_info = Column(PythonDict, default={})

    def __init__(self, **kwargs):
        named_arguments = {
            key: value for key, value in kwargs.items() if key in self.sql_columns
        }
        super().__init__(**named_arguments)
        self.extra_info = {
            key: value for key, value in kwargs.items() if key not in self.sql_columns
        }

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.creation_time,
            "cpu_usage_pct": self.cpu_usage_pct,
            "ram_usage_pct": self.ram_usage_pct,
            "free_disk_space_gb": self.free_disk_space_gb,
            "median_response_time": self.median_response_time,
            "requests_per_minute": self.requests_per_minute,
            "n_working_participants": self.n_working_participants,
            "extra_info": self.extra_info,
        }


class Experiment(dallinger.experiment.Experiment, metaclass=ExperimentMeta):
    # pylint: disable=abstract-method
    """
    The main experiment class from which to inherit when building experiments.

    Several experiment options can be set through the experiment class.
    For example, the storage back-end can be selected by setting the ``asset_storage`` attribute:

    ::

        class Exp(psynet.experiment.Experiment):

    Another experiment attribute is `export_classes_to_skip`, which is a list of classes to be excluded
    when exporting the database objects to JSON-style dictionaries. The default is `["ExperimentStatus"]`.

    Config variables can be set here, amongst other places (see online documentation for details):

    ::

        class Exp(psynet.experiment.Experiment):
            config = {
                "min_accumulated_reward_for_abort": 0.15,
                "show_abort_button": True,
            }

    Custom CSS stylesheets can be included here, to style the appearance of the experiment:

    ::

        class Exp(psynet.experiment.Experiment):
            css_links = ["static/theme.css"]

    CSS can also be included directly as part of the experiment class via the ``css`` attribute,
    see ``custom_theme`` demo for details.

    There are a number of variables tied to an experiment all of which are documented below.
    They have been assigned reasonable default values which can be overridden when defining an experiment
    (see method ``_default_variables``). Also, they can be enriched with new variables in the following way:

    ::

        import psynet.experiment

        class Exp(psynet.experiment.Experiment):
            variables = {
                "new_variable": "some-value",  # Adding a new variable
            }

    These variables can then be changed in the course of experiment, just like (e.g.) participant variables.

    ::

        from psynet.timeline import CodeBlock

        CodeBlock(lambda experiment: experiment.var.set("custom-variable", 42))

    Default experiment variables accessible through `psynet.experiment.Experiment.var` are:

    max_participant_payment : `float`
        The maximum payment in US dollars a participant is allowed to get. Default: `25.0`.

    soft_max_experiment_payment : `float`
        The recruiting process stops if the amount of accumulated payments
        (incl. time and performance rewards) in US dollars exceedes this value. Default: `1000.0`.

    hard_max_experiment_payment : `float`
        Guarantees that in an experiment no more is spent than the value assigned.
        Bonuses are not paid from the point this value is reached and a record of the amount
        of unpaid bonus is kept in the participant's `unpaid_bonus` variable. Default: `1100.0`.

    big_base_payment : `bool`
        Set this to `True` if you REALLY want to set `base_payment` to a value > 20.

    There are also a few experiment variables that are set automatically and that should,
    in general, not be changed manually:

    psynet_version : `str`
        The version of the `psynet` package.

    dallinger_version : `str`
        The version of the `Dallinger` package.

    python_version : `str`
        The version of the `Python`.

    hard_max_experiment_payment_email_sent : `bool`
        Whether an email to the experimenter has already been sent indicating the `hard_max_experiment_payment`
        had been reached. Default: `False`. Once this is `True`, no more emails will be sent about
        this payment limit being reached.

    soft_max_experiment_payment_email_sent : `bool`
        Whether an email to the experimenter has already been sent indicating the `soft_max_experiment_payment`
        had been reached. Default: `False`. Once this is `True`, no more emails will be sent about
        this payment limit being reached.


    In addition to the config variables in Dallinger, PsyNet adds the following:

    min_browser_version : `str`
        The minimum version of the Chrome browser a participant needs in order to take a HIT. Default: `80.0`.

    wage_per_hour : `float`
        The payment in currency the participant gets per hour. Default: `9.0`.

    currency : `str`
        The currency in which the participant gets paid. Default: `$`.

    min_accumulated_reward_for_abort : `float`
        The threshold of reward accumulated in US dollars for the participant to be able to receive
        compensation when aborting an experiment using the `Abort experiment` button. Default: `0.20`.

    show_abort_button : `bool`
        If ``True``, the `Ad` page displays an `Abort` button the participant can click to terminate the HIT,
        e.g. in case of an error where the participant is unable to finish the experiment. Clicking the button
        assures the participant is compensated on the basis of the amount of reward that has been accumulated.
        Default ``False``.

    show_reward : `bool`
        If ``True`` (default), then the participant's current estimated reward is displayed
        at the bottom of the page.

    show_footer : `bool`
        If ``True`` (default), then a footer is displayed at the bottom of the page containing a 'Help' button
        and reward information if `show_reward` is set to `True`.

    show_progress_bar : `bool`
        If ``True`` (default), then a progress bar is displayed at the top of the page.

    check_participant_opened_devtools : ``bool``
        If ``True``, whenever a participant opens the developer tools in the web browser,
        this is logged as participant.var.opened_devtools = ``True``,
        and the participant is shown a warning alert message.
        Default: ``False``.
        Note: Chrome does not currently expose an official way of checking whether
        the participant opens the developer tools. People therefore have to rely
        on hacks to detect it. These hacks can often be broken by updates to Chrome.
        We've therefore disabled this check by default, to reduce the risk of
        false positives. Experimenters wishing to enable the check for an individual
        experiment are recommended to verify that the check works appropriately
        before relying on it. We'd be grateful for any contributions of updated
        developer tools checks.

    window_width : ``int``
        Determines the width in pixels of the window that opens when the
        participant starts the experiment. Only active if
        recruiter.start_experiment_in_popup_window is True.
        Default: ``1024``.

    window_height : ``int``
        Determines the width in pixels of the window that opens when the
        participant starts the experiment. Only active if
        recruiter.start_experiment_in_popup_window is True.
        Default: ``768``.

    supported_locales : ``list``
        List of locales (i.e., ISO language codes) a user can pick from, e.g., ``'["en"]'``.
        Default: ``'[]'``.

    force_google_chrome : ``bool``
        Forces the user to use the Google Chrome browser. If another browser is used, it will give detailed instructions
        on how to install Google Chrome.
        Default: ``True``.

    force_incognito_mode : ``bool``
        Forces the user to open the experiment in a private browsing (i.e. incognito mode). This is helpful as incognito
        mode prevents the user from accessing their browsing history, which could be used to influence the experiment.
        Furthermore it does not enable addons which can interfere with the experiment. If the user is not using
        incognito mode, it will give detailed instructions on how to open the experiment in incognito mode.
        Default: ``False``.

    allow_mobile_devices : ``bool``
        Allows the user to use mobile devices. If it is set to false it will tell the user to open the experiment on
        their computer.
        Default: ``False``.



    Parameters
    ----------

    session:
        The experiment's connection to the database.
    """
    # Introduced this as a hotfix for a compatibility problem with macOS 10.13:
    # http://sealiesoftware.com/blog/archive/2017/6/5/Objective-C_and_fork_in_macOS_1013.html
    os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"

    export_classes_to_skip = ["ExperimentStatus"]
    initial_recruitment_size = INITIAL_RECRUITMENT_SIZE
    logos = []
    max_allowed_base_payment = 30
    max_exp_dir_size_in_mb = 256

    timeline = Timeline(InfoPage("Placeholder timeline", time_estimate=5))

    asset_storage = LocalStorage()
    css = []
    css_links = []

    __extra_vars__ = {}

    variables = {}

    def __init__(self, session=None):
        super(Experiment, self).__init__(session)

        assert isinstance(self.css, list)
        assert isinstance(self.css_links, list)

        for css_link in self.css_links:
            if not css_link.startswith("static/"):
                raise ValueError(
                    "All css_links must point to files in the experiment's static directory "
                    f" (problematic link: '{css_link}')."
                )
            if not Path(css_link).is_file():
                raise ValueError(
                    f"Couldn't find the following CSS file: {css_link}. Check ``Experiment.css_links``."
                )

        config_initial_recruitment_size = self.get_initial_recruitment_size()
        initial_recruitment_size_config_changed = (
            config_initial_recruitment_size != INITIAL_RECRUITMENT_SIZE
        )
        initial_recruitment_size_experiment_changed = (
            self.__class__.initial_recruitment_size != INITIAL_RECRUITMENT_SIZE
        )

        config = get_config()
        if self.base_payment > 10 and not config.get("big_base_payment"):
            logger.warning(f"`base_payment` is set to `{self.base_payment}`!")
        assert self.base_payment <= 20 or config.get("big_base_payment"), (
            f"Are you sure about setting `base_payment = {self.base_payment}`? "
            "You probably forgot to divide `base_payment` by 100. "
            "In the special case you REALLY want to override this behaviour, set `big_base_payment = true`"
        )

        assert not (
            initial_recruitment_size_config_changed
            and initial_recruitment_size_experiment_changed
        ), "You have set the initial recruitment size in both the config file and in your experiment class."

        if initial_recruitment_size_config_changed:
            self.initial_recruitment_size = config_initial_recruitment_size
        elif initial_recruitment_size_experiment_changed:
            raise RuntimeError(
                "You can no longer directly set the initial recruitment size in your experiment class, you need to "
                "specify it in the config.txt file or in experiment.config"
            )
        else:
            assert self.initial_recruitment_size == INITIAL_RECRUITMENT_SIZE

        if not self.label:
            raise RuntimeError(
                "PsyNet now requires you to specify a descriptive label for your experiment "
                "in your Experiment class. For example, you might write: label = 'GSP experiment with faces'"
            )

        self.database_checks = []
        self.participant_fail_routines = []
        self.recruitment_criteria = []

        self.pre_deploy_routines = []
        if self.translation_checks_needed():
            self.pre_deploy_routines.append(
                PreDeployRoutine(
                    "check_experiment_translations",
                    check_translations,
                )
            )

        self.pre_deploy_routines.append(
            PreDeployRoutine(
                "compile_translations_if_necessary",
                self.compile_translations_if_necessary,
                {
                    "locales_dir": os.path.abspath("locales"),
                    "namespace": "experiment",
                },
            )
        )

        self.process_timeline()

    @classproperty
    def launched(cls):
        return is_experiment_launched()

    @property
    def global_assets(self):
        return self.experiment_config.global_assets

    @property
    def global_nodes(self):
        return self.experiment_config.global_nodes

    @property
    def supported_locales(self):
        """
        Returns the list of supported locales for the experiment.

        This can be specified in the config.txt file, or inferred from the locales present in the locales directory.
        """
        config = get_config()
        locale = config.get("locale", "en")
        supported_locales = json.loads(config.get("supported_locales", "[]"))
        supported_locales += [locale, "en"]
        supported_locales = list(set(supported_locales))

        return supported_locales

    def translation_checks_needed(self):
        non_en_locales = [locale for locale in self.supported_locales if locale != "en"]
        return len(non_en_locales) > 0

    @classmethod
    def create_translation_template_from_experiment_folder(
        cls, input_directory, pot_path
    ):
        create_pot(input_directory, pot_path)

    @classmethod
    def _create_translation_template_from_experiment_folder(cls, locales_dir="locales"):
        os.makedirs(locales_dir, exist_ok=True)

        pot_path = os.path.join(locales_dir, "experiment.pot")
        if exists(pot_path):
            os.remove(pot_path)
        cls.create_translation_template_from_experiment_folder(os.getcwd(), pot_path)
        if not exists(pot_path):
            raise FileNotFoundError(f"Could not find pot file at {pot_path}")
        return load_po(pot_path)

    def compile_translations_if_necessary(self, locales_dir, namespace):
        """Compiles translations if necessary."""
        if self.translation_checks_needed():
            for locale in self.supported_locales:
                if locale == "en":
                    continue
                po_path = os.path.join(
                    locales_dir, locale, "LC_MESSAGES", namespace + ".po"
                )
                assert os.path.exists(po_path), f"Could not find po file at {po_path}"
                compile_mo(po_path)
        else:
            assert self.supported_locales == [
                "en"
            ], "No translations are needed, so the supported locales should be ['en']"

    def compile_psynet_translations_if_necessary(self):
        self.compile_translations_if_necessary(
            join_path(abspath(dirname(__file__)), "locales"), "psynet"
        )

    @with_transaction
    def on_launch(self):
        logger.info("Calling Exp.on_launch()...")
        self.compile_psynet_translations_if_necessary()
        redis_vars.set("launch_started", True)
        super().on_launch()
        if not deployment_info.read("redeploying_from_archive"):
            self.on_first_launch()
        self.on_every_launch()
        logger.info("Experiment launch complete!")
        db.session.commit()
        redis_vars.set("launch_finished", True)

    def on_first_launch(self):
        logger.info("Calling Exp.on_first_launch()...")
        for trialmaker in self.timeline.trial_makers.values():
            trialmaker.on_first_launch(self)

    def on_every_launch(self):
        logger.info("Calling Exp.on_every_launch()...")

        # This check is helpful to stop the database from being ingested multiple times
        # if the launch fails the first time
        deployment_db_ingested = redis_vars.get("deployment_db_ingested", False)
        print(f"deployment_db_ingested: {deployment_db_ingested}")
        if not deployment_db_ingested:
            ingest_zip(database_template_path, db.engine)
            redis_vars.set("deployment_db_ingested", True)
            assert ExperimentConfig.query.count() > 0

        self._nodes_on_deploy()

        config = dallinger_get_config()
        self.var.server_working_directory = os.getcwd()
        self.var.deployment_id = deployment_info.read("deployment_id")
        self.var.label = self.label
        if deployment_info.read("is_local_deployment"):
            # This is necessary because the local deployment command is blocking and therefore we can't
            # get the launch data from the command-line invocation.
            export_launch_data(
                self.var.deployment_id,
                dashboard_user=config.get("dashboard_user"),
                dashboard_password=config.get("dashboard_password"),
            )
        self.load_deployment_config()
        self.asset_storage.on_every_launch()

    @staticmethod
    def before_request():
        flask_app_globals.request_start_time = time.monotonic()

    @staticmethod
    def after_request(request, response):
        diff = time.monotonic() - flask_app_globals.request_start_time
        relevant_endpoints = [
            "/ad",
            "/consent",
            "/on-demand-asset",
            "/response",
            "/start",
            "/timeline",
        ]
        if any([endpoint == request.path for endpoint in relevant_endpoints]):
            params = dict(request.args)
            request_obj = Request(
                unique_id=params.get("unique_id", None),
                duration=diff,
                method=request.method,
                endpoint=request.path,
                params=params,
            )
            db.session.add(request_obj)
            db.session.commit()
        return response

    @classmethod
    def get_request_statistics(cls, lookback):
        now = datetime.now()
        lookback = now - pd.Timedelta(lookback)
        all_requests = Request.query.filter(Request.creation_time > lookback).all()
        requests_df = pd.DataFrame([request.to_dict() for request in all_requests])
        summary = {}
        if len(requests_df) > 0:
            summary["median_response_time"] = float(requests_df["duration"].median())
            summary["requests_per_minute"] = len(requests_df)
        return summary

    @classmethod
    def get_recruiter_status(cls):
        exp = get_experiment()
        status = exp.recruiter.get_status()
        if isinstance(status, dict):
            return status
        elif isinstance(status, RecruitmentStatus):
            return vars(status)
        else:
            raise ValueError(
                f"Unknown status type: {type(status)}. Must be one of: dict, RecruitmentStatus"
            )

    @classmethod
    def get_hardware_status(cls):
        return {
            "cpu_usage_pct": psutil.cpu_percent(),
            "ram_usage_pct": psutil.virtual_memory().percent,
            "free_disk_space_gb": psutil.disk_usage("/").free / (2**30),
        }

    @classmethod
    def get_status(cls, lookback="10s"):
        return {
            **super().get_status(),
            **cls.get_request_statistics(lookback=lookback),
            **cls.get_hardware_status(),
            **cls.get_recruiter_status(),
        }

    @scheduled_task("interval", seconds=10, max_instances=1)
    @staticmethod
    def check_experiment_status():
        exp = get_experiment()
        status_dict = exp.get_status(lookback="10s")  # since we poll every minute
        status_obj = ExperimentStatus(**status_dict)
        db.session.add(status_obj)
        db.session.commit()

    def load_deployment_config(self):
        config = dallinger_get_config()
        if not config.ready:
            config.load()
        self.var.deployment_config = {
            key: value
            for section in reversed(config.data)
            for key, value in section.items()
            if not config.is_sensitive(key)
        }

    def _nodes_on_deploy(self):
        from .trial.main import TrialNode

        db.session.commit()

        for node in (
            TrialNode.query.with_for_update(of=TrialNode).populate_existing().all()
        ):
            node.check_on_deploy()

        db.session.commit()

    def participant_constructor(self, *args, **kwargs):
        return Participant(experiment=self, *args, **kwargs)

    def initialize_bot(self, bot):
        """
        This function is called when a bot is created.
        It can be used to set stochastic random parameters corresponding
        to participant latent traits, for example.

        e.g.

        ```bot.var.musician = True``
        """
        pass

    test_n_bots = 1
    test_mode = "serial"
    test_real_time = False

    def test_experiment(self):
        os.environ["PASSTHROUGH_ERRORS"] = "True"
        os.environ["DEPLOYMENT_PACKAGE"] = "True"

        if self.test_mode == "serial" or self.test_n_bots == 1:
            self._test_experiment_serial()
        elif self.test_mode == "parallel":
            self._test_experiment_parallel()
        else:
            raise ValueError(f"Invalid test mode: {self.test_mode}")

    # This is how many seconds to wait between invoking parallel bots
    test_parallel_stagger_interval_s = 0.1

    def _test_experiment_parallel(self):
        # Start N subprocesses, and in each one call `psynet run-bot`
        logger.info(f"Testing experiment with {self.test_n_bots} parallel bots...")

        n_processes = self.test_n_bots

        processes = []
        process_ids = list(range(n_processes))
        bot_ids = [process_id + 1 for process_id in process_ids]

        cmd = "psynet run-bot"
        if self.test_real_time:
            cmd += " --real-time"

        for bot_id in bot_ids:
            if bot_id > 0:
                time.sleep(self.test_parallel_stagger_interval_s)

            logger.info(f"Creating and running bot {bot_id}...")
            p = pexpect.spawn(cmd, timeout=None, cwd=None)
            processes.append(p)

        waiting_for_processes = True
        finished_processes = set()

        testing_stats = self.TestingStats(self.testing_stat_definitions)

        while waiting_for_processes:
            for process, process_id, bot_id in zip(processes, process_ids, bot_ids):
                try:
                    while True:
                        output = (
                            process.read_nonblocking(size=100000, timeout=0)
                            .decode()
                            .strip()
                            .split("\n")
                        )
                        for line in output:
                            line.replace("INFO:root:", "")
                            logger.info(f"(Bot {bot_id}) " + line)

                            testing_stats.update_from_line(bot_id, line)

                        time.sleep(0.01)
                except pexpect.TIMEOUT:
                    pass
                except pexpect.EOF:
                    assert process.exitstatus == 0
                    finished_processes.add(process_id)

            if len(finished_processes) == n_processes:
                waiting_for_processes = False

        bots = Bot.query.all()
        self.test_check_bots(bots)

        testing_stats.report()

    class TestingStats:
        def __init__(self, stat_definitions):
            self.stat_definitions = stat_definitions
            self.data = {
                stat_definition.key: {} for stat_definition in stat_definitions
            }

        def update_from_line(self, bot_id, line):
            for stat_definition in self.stat_definitions:
                stat = stat_definition.extract_stat(line)
                if stat is not None:
                    self.update_from_stat(stat_definition.key, bot_id, stat)

        def update_from_stat(self, stat_key, bot_id, value):
            self.data[stat_key][bot_id] = value

        def report(self):
            logger.info("BOT TESTING STATISTICS:")
            for stat_definition in self.stat_definitions:
                values = self.data[stat_definition.key].values()
                stat_definition.report(values)

    class TestingStatDefinition:
        def __init__(self, key, label, regex, suffix, decimal_places=3):
            self.key = key
            self.label = label
            self.regex = regex
            self.suffix = suffix
            self.decimal_places = decimal_places

        def extract_stat(self, line):
            match = re.search(self.regex, line)
            if match:
                return float(match.group(1))

        def report(self, values):
            values_not_none = [value for value in values if value is not None]

            if len(values_not_none) > 0:
                _mean = mean(values_not_none)
                template = f"Mean %s = %.{self.decimal_places}f%s"
                logger.info(template % (self.label, _mean, self.suffix))
            else:
                logger.info(f"Didn't find any values for {self.label} to report.")

    testing_stat_definitions = [
        TestingStatDefinition(
            "progress",
            label="progress through experiment",
            regex="progress = ([0-9]*)%",
            suffix="%",
            decimal_places=0,
        ),
        TestingStatDefinition(
            "mean_processing_time",
            label="processing time per page",
            regex="mean processing time per page = ([0-9]*\\.[0-9]*) seconds",
            suffix=" seconds",
        ),
        TestingStatDefinition(
            "total_wait_page_time",
            label="total wait page time per bot",
            regex="total WaitPage time = ([0-9]*\\.[0-9]*) seconds",
            suffix=" seconds",
            decimal_places=2,
        ),
        TestingStatDefinition(
            "total_experiment_time",
            label="time taken to complete experiment",
            regex="total experiment time = ([0-9]*\\.[0-9]*) seconds",
            suffix=" seconds",
        ),
    ]

    def _test_experiment_serial(self):
        logger.info(f"Testing experiment with {self.test_n_bots} serial bot(s)...")
        bots = [Bot() for _ in range(self.test_n_bots)]
        self.test_serial_run_bots(bots)
        self.test_check_bots(bots)

    def test_serial_run_bots(self, bots):
        for bot in bots:
            db.session.add(bot)  # Protects against DetachedInstanceErrors
            self.run_bot(bot)

    def run_bot(self, bot):
        time_factor = float(self.test_real_time)
        if time_factor > 0:
            warnings.warn(
                "Real-time mode doesn't seem to work well at present; take results with a pinch of salt.",
                DeprecationWarning,
            )
        bot.take_experiment(render_pages=True, time_factor=time_factor)

    def test_check_bots(self, bots: List[Bot]):
        for b in bots:
            self.test_check_bot(b)

    def test_check_bot(self, bot: Bot, **kwargs):
        assert not bot.failed

    @classmethod
    def error_page(
        cls,
        participant=None,
        error_text=None,
        recruiter=None,
        external_submit_url=None,
        compensate=True,
        error_type="default",
        request_data="",
        locale=DEFAULT_LOCALE,
    ):
        """Render HTML for error page."""
        from flask import make_response, request

        _p = get_translator(context=True)
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
                "psynet_error.html",
                locale=locale,
                error_text=error_text,
                compensate=compensate,
                contact_address=get_config().get("contact_email_on_error"),
                error_type=error_type,
                hit_id=hit_id,
                assignment_id=assignment_id,
                worker_id=worker_id,
                recruiter=recruiter,
                request_data=request_data,
                participant_id=participant_id,
                external_submit_url=external_submit_url,
            ),
            500,
        )

    def error_page_content(
        self,
        contact_address,
        error_type,
        hit_id,
        assignment_id,
        worker_id,
        external_submit_url,
    ):
        _ = get_translator()
        _p = get_translator(context=True)

        if hasattr(self.recruiter, "error_page_content"):
            return self.recruiter.error_page_content(
                assignment_id=assignment_id,
                external_submit_url=external_submit_url,
            )

        # TODO: Refactor this so that the error page content generation is deferred to the recruiter class.
        if isinstance(self.recruiter, ProlificRecruiter):
            return self.error_page_content__prolific()
        elif isinstance(self.recruiter, MTurkRecruiter):
            html = tags.div()
            with html:
                tags.p(
                    _p(
                        "mturk_error",
                        "To enquire about compensation, please contact the researcher at {EMAIL} and describe what led to this error.",
                    ).format(EMAIL=contact_address)
                )
                tags.p(
                    _p("mturk_error", "Please also quote the following information:")
                )
                tags.ul(
                    tags.li(f'{_("Error type")}: {error_type}'),
                    tags.li(f'{_("HIT ID")}: {hit_id}'),
                    tags.li(f'{_("Assignment ID")}: {assignment_id}'),
                    tags.li(f'{_("Worker ID")}: {worker_id}'),
                )

            return html
        else:
            return ""

    def error_page_content__prolific(self):
        _p = get_translator(context=True)

        html = tags.div()
        with html:
            tags.p(
                " ".join(
                    [
                        _p(
                            "prolific_error",
                            "Don't worry, your progress has been recorded.",
                        ),
                        _p(
                            "prolific_error",
                            "To enquire about compensation, please send the researcher a message via the Prolific website and describe what led to your error.",
                        ),
                    ]
                )
            )
        return html

    @scheduled_task("interval", minutes=1, max_instances=1)
    @staticmethod
    @with_transaction
    def check_database():
        if not is_experiment_launched():
            return
        exp = get_experiment()
        for c in exp.database_checks:
            c.run()

    @scheduled_task("interval", minutes=1, max_instances=1)
    @staticmethod
    @with_transaction
    def run_recruiter_checks():
        if not is_experiment_launched():
            return
        exp = get_experiment()
        recruiter = exp.recruiter
        logger.info("Running recruiter checks...")
        if hasattr(recruiter, "run_checks"):
            recruiter.run_checks()

    @scheduled_task("interval", seconds=2, max_instances=1)
    @log_time_taken
    @staticmethod
    @with_transaction
    def _grow_networks():
        if not is_experiment_launched():
            return
        exp = get_experiment()
        exp.grow_networks()

    @staticmethod
    def grow_networks():
        # A bit of a hack that we only grow ChainNetworks here, we might need to extend this to
        # cover other types of networks in the future.
        from psynet.trial.chain import ChainNetwork

        # This query could be further optimized by identifying which network classes are present in the table
        # and making queries specific to these. This would allow subclass-specific attributes to be loaded
        # in the initial query rather than being lazily loaded.
        networks = (
            ChainNetwork.query.filter(
                ChainNetwork.ready_to_spawn,
                ChainNetwork.chain_type
                != "within",  # participants are responsible for growing within-networks
            )
            .with_for_update()
            .populate_existing()
            .options(joinedload(ChainNetwork.head, innerjoin=True))
            .all()
        )
        if len(networks) > 0:
            logger.info("Growing %i networks...", len(networks))
            exp = get_experiment()
            for network in networks:
                try:
                    network.grow(experiment=exp)
                except Exception as err:
                    if not isinstance(err, exp.HandledError):
                        exp.handle_error(
                            err,
                            network=network,
                        )
                    if network.head.degree > 0:
                        network.head.fail()
                    elif network.head.degree == 0:
                        for trial in network.head.all_trials:
                            trial.fail()

            logger.info("Finished growing networks.")

    @scheduled_task("interval", seconds=0.5, max_instances=1)
    @log_time_taken
    @staticmethod
    @with_transaction
    def _check_barriers():
        if not is_experiment_launched():
            return
        exp = get_experiment()
        exp.check_barriers()

    @staticmethod
    def check_barriers():
        from .sync import ParticipantLinkBarrier

        barrier_links = (
            ParticipantLinkBarrier.query.join(Participant)
            .filter(
                ~ParticipantLinkBarrier.released,
                ~Participant.failed,
                Participant.status == "working",
            )
            # We need to lock Participant rows to prevent race conditions with participants
            # who are currently being processed in other tasks
            # (e.g. advancing through the timeline).
            .with_for_update(of=[ParticipantLinkBarrier, Participant])
            .populate_existing()
            .all()
        )

        # Before we used a DISTINCT clause --
        # .distinct(ParticipantLinkBarrier.barrier_id)
        # but DISTINCT is incompatible with FOR UPDATE in Postgres.
        # We therefore do this filtering in Python instead.
        processed_barriers = set()
        for link in barrier_links:
            if link.barrier_id not in processed_barriers:
                barrier = link.get_barrier()
                barrier.process_potential_releases()
                processed_barriers.add(link.barrier_id)

    @scheduled_task("interval", seconds=2.5, max_instances=1)
    @log_time_taken
    @staticmethod
    @with_transaction
    def _check_sync_groups():
        if not is_experiment_launched():
            return
        exp = get_experiment()
        exp.check_sync_groups()

    @staticmethod
    def check_sync_groups():
        from .sync import SyncGroup

        groups = (
            # Eagerly load all polymorphic subclasses to avoid lazy loading in the loop
            db.session.query(with_polymorphic(SyncGroup, "*"))
            .filter(SyncGroup.active)
            # TODO - see if we can introduce this locking once the transaction managemnet in the tests is fixed
            # .with_for_update(of=[SyncGroup, Participant])
            .with_for_update(of=[SyncGroup])
            .populate_existing()
            .all()
        )

        for group in groups:
            group.check_numbers()

    @property
    def base_payment(self):
        return get_config().get("base_payment")

    @property
    def variable_placeholders(self):
        return {}

    def get_initial_recruitment_size(self):
        return get_config().get("initial_recruitment_size")

    @classproperty
    def label(cls):  # noqa
        return get_config().get("label")

    @property
    def var(self):
        if self.experiment_config:
            return self.experiment_config.var
        else:
            return ImmutableVarStore(self.variables_initial_values)

    # We persist _experiment_config to avoid garbage collection and hence support database updates
    _experiment_config = None

    @property
    def experiment_config(self):
        self._experiment_config = ExperimentConfig.query.get(1)
        return self._experiment_config

    def register_participant_fail_routine(self, routine):
        self.participant_fail_routines.append(routine)

    def register_recruitment_criterion(self, criterion):
        self.recruitment_criteria.append(criterion)

    def register_database_check(self, task):
        self.database_checks.append(task)

    @classmethod
    def new(cls, session):
        return cls(session)

    @classmethod
    def amount_spent(cls):
        return sum(
            [
                (0.0 if p.base_payment is None else p.base_payment)
                + (0.0 if p.bonus is None else p.bonus)
                for p in Participant.query.all()
            ]
        )

    @classmethod
    def estimated_max_reward(cls, wage_per_hour):
        return cls.timeline.estimated_max_reward(wage_per_hour)

    @classmethod
    def estimated_completion_time(cls, wage_per_hour):
        return cls.timeline.estimated_completion_time(wage_per_hour)

    def setup_experiment_config(self):
        if self.experiment_config is None:
            logger.info("Setting up ExperimentConfig.")
            network = ExperimentConfig()
            db.session.add(network)
            db.session.commit()

    @classproperty
    def config(cls):
        return {}

    @classmethod
    def get_experiment_folder_name(cls):
        try:
            return deployment_info.read("folder_name")
        except (KeyError, FileNotFoundError):
            return os.path.basename(os.getcwd())

    @classmethod
    def config_defaults(cls):
        """
        Override this classmethod to register new default values for config variables.
        Remember to call super!
        """

        config = {
            **super().config_defaults(),
            "allow_mobile_devices": False,
            "base_payment": 0.10,
            "big_base_payment": False,
            "check_dallinger_version": True,
            "clock_on": True,
            "color_mode": "light",
            "currency": "$",
            "default_translator": "chat_gpt",
            "disable_browser_autotranslate": True,
            "disable_when_duration_exceeded": False,
            "docker_volumes": "${HOME}/psynet-data/assets:/psynet-data/assets",
            "duration": 100000000.0,
            "force_google_chrome": True,
            "force_incognito_mode": False,
            "openai_default_model": "gpt-4o",
            "openai_default_temperature": 0,
            "host": "0.0.0.0",
            "initial_recruitment_size": INITIAL_RECRUITMENT_SIZE,
            "label": cls.get_experiment_folder_name(),
            "lock_table_when_creating_participant": False,
            "loglevel_worker": 1,
            "min_accumulated_reward_for_abort": 0.20,
            "min_browser_version": "80.0",
            "prolific_is_custom_screening": False,
            "protected_routes": json.dumps(_protected_routes),
            "show_abort_button": False,
            "show_footer": True,
            "show_progress_bar": True,
            "show_reward": True,
            "check_participant_opened_devtools": False,
            "supported_locales": "[]",
            "wage_per_hour": 9.0,
            "window_height": 768,
            "window_width": 1024,
            **cls.config,
        }

        config_types = dallinger_get_config().types

        for key, value in config.items():
            if not isinstance(value, (bool, int, float, str)):
                # Dallinger expects non-primitive types to be expressed as JSON-encoded strings.
                # We should probably update this behavior in the future.
                value = serialize(value)

            expected_type = config_types[key]
            value = expected_type(value)

            config[key] = value

        return config

    @property
    def _default_variables(self):
        return {
            "psynet_version": __version__,
            "dallinger_version": dallinger_version,
            "python_version": python_version(),
            "hard_max_experiment_payment_email_sent": False,
            "soft_max_experiment_payment_email_sent": False,
            "hard_max_experiment_payment": 1100.0,
            "soft_max_experiment_payment": 1000.0,
            "max_participant_payment": 25.0,
        }

    @experiment_route("/api/<endpoint>", methods=["GET", "POST"])
    @staticmethod
    @with_transaction
    def custom_route(endpoint):
        from psynet.api import EXPOSED_FUNCTIONS

        if endpoint not in EXPOSED_FUNCTIONS:
            return error_response(
                error_text=f"{endpoint} is not defined. Defined endpoints are: {list(EXPOSED_FUNCTIONS.keys())}",
                simple=True,
            )

        if request.method == "POST":
            data = request.get_json()
        elif request.method == "GET":
            data = request.args
        else:
            return error_response(
                error_text=f"Unsupported request method {request.method}", simple=True
            )
        function = EXPOSED_FUNCTIONS[endpoint]
        return function(**data)

    @property
    def psynet_logo(self):
        return PsyNetLogo()

    @property
    def start_experiment_in_popup_window(self):
        if self.var.has("start_experiment_in_popup_window"):
            # This is for simulating pop up behaviour in psynet demo tests
            return self.var.get("start_experiment_in_popup_window")
        elif hasattr(self.recruiter, "start_experiment_in_popup_window"):
            return self.recruiter.start_experiment_in_popup_window
        elif isinstance(self.recruiter, MTurkRecruiter):
            return True

        else:
            return False

    @property
    def description(self):
        return get_config().get("description")

    @property
    def ad_requirements(self):
        return [
            'The experiment can only be performed using a <span style="font-weight: bold;">laptop</span> (desktop computers are not allowed).',
            'You should use an <span style="font-weight: bold;">updated Google Chrome</span> browser.',
            'You should be sitting in a <span style="font-weight: bold;">quiet environment</span>.',
            'You should be at least <span style="font-weight: bold;">18 years old</span>.',
            'You should be a <span style="font-weight: bold;">fluent English speaker</span>.',
        ]

    @property
    def ad_payment_information(self):
        return f"""
                We estimate that the task should take approximately <span style="font-weight: bold;">{round(self.estimated_duration_in_minutes)} minutes</span>. Upon completion of the full task,
                <br>
                you should receive a reward of approximately
                <span style="font-weight: bold;">${'{:.2f}'.format(self.estimated_reward_in_dollars)}</span> depending on the
                amount of work done.
                <br>
                In some cases, the experiment may finish early: this is not an error, and there is no need to write to us.
                <br>
                In this case you will be paid in proportion to the amount of the experiment that you completed.
                """

    @property
    def variables_initial_values(self):
        for key, value in self.variables.items():
            assert key not in list(get_config().as_dict().keys()), (
                f"Variable {key} is a config variable and should solely be specified in the config.txt or in "
                "experiment.config but NOT as experiment variable."
            )
        return {**self._default_variables, **self.variables}

    @property
    def estimated_duration_in_minutes(self):
        return self.timeline.estimated_time_credit.get_max("time") / 60

    @property
    def estimated_reward_in_dollars(self):
        wage_per_hour = get_config().get("wage_per_hour")
        return round(
            self.timeline.estimated_time_credit.get_max(
                "reward",
                wage_per_hour=wage_per_hour,
            ),
            2,
        )

    def setup_experiment_variables(self):
        # Note: the experiment network must be setup first before we can set these variables.
        log(
            "Initializing experiment with variables \n"
            + pretty_log_dict(self.variables_initial_values, 4)
        )

        for key, value in self.variables_initial_values.items():
            self.var.set(key, value)

        db.session.commit()

    # def prepare_generic_trial_network(self):
    #     network = GenericTrialNetwork(experiment=self)
    #     source = GenericTrialNode(network=network)
    #     db.session.add(network)
    #     db.session.add(source)
    #     db.session.commit()

    def process_timeline(self):
        for elt in self.timeline.elts:
            if isinstance(elt, DatabaseCheck):
                self.register_database_check(elt)
            if isinstance(elt, ParticipantFailRoutine):
                self.register_participant_fail_routine(elt)
            if isinstance(elt, RecruitmentCriterion):
                self.register_recruitment_criterion(elt)
            if isinstance(elt, Asset):
                elt.deposit_on_the_fly = False
                self.assets.stage(elt)
            if isinstance(elt, PreDeployRoutine):
                self.pre_deploy_routines.append(elt)

    def pre_deploy(self):
        self.update_deployment_id()
        self.setup_experiment_config()
        self.setup_experiment_variables()

        for module in self.timeline.modules.values():
            module.prepare_for_deployment(experiment=self)

        for routine in self.pre_deploy_routines:
            logger.info(f"Running pre-deployment routine '{routine.label}'...")
            call_function_with_context(
                routine.function, experiment=self, **routine.args
            )

        self.assets.prepare_for_deployment()
        self.create_database_snapshot()
        self.create_source_code_zip_file()

    @classmethod
    def create_source_code_zip_file(cls):
        from dallinger.command_line.utils import ExperimentFileSource
        from yaspin import yaspin

        # The config.txt file in the deployment package by default includes sensitive keys
        # (e.g. AWS API keys), so we don't allow this method to be run there
        assert not in_deployment_package()

        # We also need to check that the user hasn't left any sensitive keys in the
        # config.txt in their experiment directory.
        assert_config_txt_does_not_contain_sensitive_values()

        base_name = "source_code"
        with yaspin(
            text=f"Saving a snapshot of the experiment source code to {base_name}.zip ...",
            color="green",
        ) as spinner:
            with tempfile.TemporaryDirectory() as temp_dir:
                cwd = os.getcwd()
                ExperimentFileSource(cwd).apply_to(temp_dir, copy_func=shutil.copyfile)
                # `ExperimentFileSource` does not include `config.txt` (see `dallinger.utils.exclusion_policy`)
                # so we need to copy this manually.
                shutil.copyfile(f"{cwd}/config.txt", f"{temp_dir}/config.txt")
                shutil.make_archive(base_name, "zip", temp_dir)
            spinner.ok("✔")

    @classmethod
    def update_deployment_id(cls):
        deployment_id = cls.generate_deployment_id()
        deployment_info.write(deployment_id=deployment_id)

    @classmethod
    def generate_deployment_id(cls):
        mode = deployment_info.read("mode")
        id_ = f"{cls.label}"
        id_ = id_.replace(" ", "-").lower()
        id_ += (
            "__mode="
            + mode
            + "__launch="
            + datetime.now().strftime("%Y-%m-%d--%H-%M-%S")
        )
        return id_

    @property
    def deployment_id(self):
        return deployment_info.read("deployment_id")

    @classmethod
    def create_database_snapshot(cls):
        logger.info("Creating a database snapshot...")
        try:
            os.remove(database_template_path)
        except FileNotFoundError:
            pass
        with tempfile.TemporaryDirectory() as temp_dir:
            with working_directory(temp_dir):
                dallinger.data.export("app", local=True, scrub_pii=False)
            shutil.copyfile(
                os.path.join(temp_dir, "data", "app-data.zip"),
                database_template_path,
            )

    @classmethod
    def check_size(cls):
        from dallinger.command_line.utils import ExperimentFileSource

        size_in_mb = ExperimentFileSource(os.getcwd()).size / (1024**2)
        log(f"Experiment directory size: {round(size_in_mb, 3)} MB.")

        if size_in_mb > cls.max_exp_dir_size_in_mb:
            raise RuntimeError(
                f"Your experiment source package exceeds the {cls.max_exp_dir_size_in_mb} MB limit. "
                "Large packages are discouraged because they make deployment slow. You can override "
                "this limit by setting `Experiment.max_exp_dir_size_in_mb` to a higher number in your "
                "`Experiment` class. However, the recommended approach (assuming your large files are "
                "assets, such as audio or video files) is to use PsyNet's asset management system; "
                "see https://psynetdev.gitlab.io/PsyNet/tutorials/assets.html for a tutorial. "
                "Importantly, you should either move your large files outside the experiment folder, "
                "or add them to `.gitignore`, once they are registered as `Asset` objects; that way "
                "they will not count towards your source package limit."
            )

    @classmethod
    def check_config(cls):
        config = get_config()

        if not config.get("clock_on"):
            # We force the clock to be on because it's necessary for the check_networks functionality.
            raise RuntimeError(
                "PsyNet requires the clock process to be enabled; please set clock_on = true in the "
                + "'[Server]' section of the config.txt."
            )

        if config.get("disable_when_duration_exceeded"):
            raise RuntimeError(
                "PsyNet requires disable_when_duration_exceeded = False; please set disable_when_duration_exceeded = False "
                + " in the '[Recruitment strategy]' section of the config.txt."
            )

        n_char_title = len(config.get("title"))
        if n_char_title > 128:
            raise RuntimeError(
                f"The maximum title length is 128 characters (current = {n_char_title}), please fix this in config.txt."
            )

        cls.check_base_payment(config)

        parser = configparser.ConfigParser()
        parser.read("config.txt")
        config_txt = {}

        for section in parser.sections():
            config_txt.update(dict(parser.items(section)))

        for key in cls.config:
            if key in config_txt:
                raise ValueError(
                    f"Config variable {key} was registered both in config.txt and experiment.py. "
                    f"Please choose just one location."
                )

    @classmethod
    def check_base_payment(cls, config):
        if config.get("base_payment") > cls.max_allowed_base_payment:
            raise ValueError(
                f"Your experiment's `base_payment` exceeds the maximum allowed value of {cls.max_allowed_base_payment}!\n\n"
                "Check that you have the units right; for example, if your currency is dollars, then base payment "
                "should be specified in dollars, not cents. If you're sure you want this large base payment, "
                "then set `Experiment.max_allowed_base_payment` to a larger value in experiment.py."
            )

    @property
    def num_working_participants(self):
        return Participant.query.filter_by(status="working", failed=False).count()

    def recruit(self):
        if self.need_more_participants:
            logger.info("Conclusion: recruiting another participant.")
            self.recruiter.recruit(n=1)
        else:
            logger.info("Conclusion: no recruitment required.")
            self.recruiter.close_recruitment()

    @property
    def need_more_participants(self):
        if self.amount_spent() >= self.var.soft_max_experiment_payment:
            self.ensure_soft_max_experiment_payment_email_sent()
            return False

        need_more = False
        for i, criterion in enumerate(self.recruitment_criteria):
            logger.info(
                "Evaluating recruitment criterion %i/%i...",
                i + 1,
                len(self.recruitment_criteria),
            )
            res = call_function(criterion.function, experiment=self)
            assert isinstance(res, bool)
            logger.info(
                "Recruitment criterion %i/%i ('%s') %s.",
                i + 1,
                len(self.recruitment_criteria),
                criterion.label,
                (
                    "returned True (more participants needed)."
                    if res
                    else "returned False (no more participants needed)."
                ),
            )
            if res:
                need_more = True
        return need_more

    def ensure_hard_max_experiment_payment_email_sent(self):
        if not self.var.hard_max_experiment_payment_email_sent:
            self.send_email_hard_max_payment_reached()
            self.var.hard_max_experiment_payment_email_sent = True

    def send_email_hard_max_payment_reached(self):
        config = get_config()
        template = """Dear experimenter,

            This is an automated email from PsyNet. You are receiving this email because
            the total amount spent in the experiment has reached the HARD maximum of ${hard_max_experiment_payment}.
            Working participants' bonuses will not be paid out. Instead, the amount of unpaid
            bonus is saved in the participant's `unpaid_bonus` variable.

            The application id is: {app_id}

            To see the logs, use the command "dallinger logs --app {app_id}"
            To pause the app, use the command "dallinger hibernate --app {app_id}"
            To destroy the app, use the command "dallinger destroy --app {app_id}"

            The PsyNet developers.
            """
        message = {
            "subject": "HARD maximum experiment payment reached.",
            "body": template.format(
                hard_max_experiment_payment=self.var.hard_max_experiment_payment,
                app_id=config.get("id"),
            ),
        }
        logger.info(
            f"HARD maximum experiment payment "
            f"of ${self.var.hard_max_experiment_payment} reached!"
        )
        try:
            admin_notifier(config).send(**message)
        except SMTPAuthenticationError as e:
            logger.error(
                f"SMTPAuthenticationError sending 'hard_max_experiment_payment' reached email: {e}"
            )
        except Exception as e:
            logger.error(
                f"Unknown error sending 'hard_max_experiment_payment' reached email: {e}"
            )

    def ensure_soft_max_experiment_payment_email_sent(self):
        if not self.var.soft_max_experiment_payment_email_sent:
            self.send_email_soft_max_payment_reached()
            self.var.soft_max_experiment_payment_email_sent = True

    def send_email_soft_max_payment_reached(self):
        config = get_config()
        template = """Dear experimenter,

            This is an automated email from PsyNet. You are receiving this email because
            the total amount spent in the experiment has reached the soft maximum of ${soft_max_experiment_payment}.
            Recruitment ended.

            The application id is: {app_id}

            To see the logs, use the command "dallinger logs --app {app_id}"
            To pause the app, use the command "dallinger hibernate --app {app_id}"
            To destroy the app, use the command "dallinger destroy --app {app_id}"

            The PsyNet developers.
            """
        message = {
            "subject": "Soft maximum experiment payment reached.",
            "body": template.format(
                soft_max_experiment_payment=self.var.soft_max_experiment_payment,
                app_id=config.get("id"),
            ),
        }
        logger.info(
            f"Recruitment ended. Maximum experiment payment "
            f"of ${self.var.soft_max_experiment_payment} reached!"
        )
        try:
            admin_notifier(config).send(**message)
        except SMTPAuthenticationError as e:
            logger.error(
                f"SMTPAuthenticationError sending 'soft_max_experiment_payment' reached email: {e}"
            )
        except Exception as e:
            logger.error(
                f"Unknown error sending 'soft_max_experiment_payment' reached email: {e}"
            )

    def is_complete(self):
        return (not self.need_more_participants) and self.num_working_participants == 0

    def assignment_abandoned(self, participant):
        participant.append_failure_tags("assignment_abandoned", "premature_exit")
        super().assignment_abandoned(participant)

    def assignment_returned(self, participant):
        participant.append_failure_tags("assignment_returned", "premature_exit")
        super().assignment_returned(participant)

    def assignment_reassigned(self, participant):
        participant.append_failure_tags("assignment_reassigned", "premature_exit")
        super().assignment_reassigned(participant)

    def bonus(self, participant):
        """
        Calculates and returns the reward the given participant gets when
        completing the experiment.

        :param participant:
            The participant.
        :type participant:
            :attr:`~psynet.participant.Participant`
        :returns:
            The reward as a ``float``.
        """
        reward = participant.calculate_reward()
        return self.check_bonus(reward, participant)

    def check_bonus(self, reward, participant):
        """
        Ensures that a participant receives no more than a reward of max_participant_payment.
        Additionally, checks if both soft_max_experiment_payment or max_participant_payment have
        been reached or exceeded, respectively. Emails are sent out warning the user if either is true.

        :param reward: float
            The reward calculated in :func:`~psynet.experiment.Experiment.bonus()`.
        :type participant:
            :attr: `~psynet.participant.Participant`
        :returns:
            The possibly reduced reward as a ``float``.
        """

        # check hard_max_experiment_payment
        if (
            self.var.hard_max_experiment_payment_email_sent
            or self.amount_spent() + self.outstanding_base_payments() + reward
            > self.var.hard_max_experiment_payment
        ):
            participant.var.set("unpaid_bonus", reward)
            self.ensure_hard_max_experiment_payment_email_sent()

        # check soft_max_experiment_payment
        if self.amount_spent() + reward >= self.var.soft_max_experiment_payment:
            self.ensure_soft_max_experiment_payment_email_sent()

        # check max_participant_payment
        if participant.amount_paid() + reward > self.var.max_participant_payment:
            reduced_reward = round(
                self.var.max_participant_payment - participant.amount_paid(), 2
            )
            participant.send_email_max_payment_reached(self, reward, reduced_reward)
            return reduced_reward
        return reward

    def outstanding_base_payments(self):
        return self.num_working_participants * self.base_payment

    def with_lucid_recruitment(self):
        return issubclass(self.recruiter.__class__, BaseLucidRecruiter)

    def with_prolific_recruitment(self):
        return issubclass(self.recruiter.__class__, ProlificRecruiter)

    def process_response(
        self,
        participant_id,
        raw_answer,
        blobs,
        metadata,
        page_uuid,
        client_ip_address,
        answer=NoArgumentProvided,
    ):
        logger.info(
            f"Received a response from participant {participant_id} on page {page_uuid}."
        )
        participant = (
            Participant.query.with_for_update(of=Participant)
            .populate_existing()
            .get(participant_id)
        )

        if page_uuid != participant.page_uuid:
            raise RuntimeError(
                f"Participant {participant_id} tried to submit data with the wrong page_uuid"
                + f"(submitted = {page_uuid}, required = {participant.page_uuid})."
            )

        try:
            event = self.timeline.get_current_elt(self, participant)
            response = event.process_response(
                raw_answer=raw_answer,
                blobs=blobs,
                metadata=metadata,
                experiment=self,
                participant=participant,
                client_ip_address=client_ip_address,
                answer=answer,
            )
            validation = event.validate(
                response=response,
                answer=response.answer,
                raw_answer=raw_answer,
                participant=participant,
                experiment=self,
                page=event,
            )
            if isinstance(validation, str):
                validation = FailedValidation(message=validation)
            response.successful_validation = not isinstance(
                validation, FailedValidation
            )
            if not response.successful_validation:
                return self.response_rejected(message=validation.message)

            participant.inc_time_credit(event.time_estimate)
            participant.inc_progress(event.time_estimate)

            self.timeline.advance_page(self, participant)
            return self.response_approved(participant)
        except Exception as err:
            if os.getenv("PASSTHROUGH_ERRORS"):
                raise
            if not isinstance(err, self.HandledError):
                self.handle_error(
                    err,
                    participant=participant,
                    trial=participant.current_trial,
                    node=(
                        participant.current_trial.node
                        if participant.current_trial
                        else None
                    ),
                    network=(
                        participant.current_trial.network
                        if participant.current_trial
                        else None
                    ),
                )
            return error_response(participant=participant)

    def response_approved(self, participant):
        logger.debug("The response was approved.")
        page = self.timeline.get_current_elt(self, participant)
        return success_response(submission="approved", page=page.__json__(participant))

    def response_rejected(self, message):
        logger.warning(
            "The response was rejected with the following message: '%s'.", message
        )
        return success_response(submission="rejected", message=message)

    def render_exit_message(self, participant):
        """
        This method is currently only called if the 'generic' recruiter is selected.
        We may propagate it to other recruiter methods eventually too.
        If left unchanged, the default recruiter exit message from Dallinger will be shown.
        Otherwise, one can return a custom message in various ways.
        If you return a string, this will be escaped appropriately and presented as text.
        Alternatively, more complex HTML structures can be constructed using the
        Python package ``dominate``, see Examples for details.

        Examples
        --------

        This would be appropriate for experiments with no payment:

        ::

            tags.div(
                tags.p("Thank you for participating in this experiment!"),
                tags.p("Your responses have been saved. You may close this window."),
            )

        This kind of structure could be used for passing participants to a particular
        URL in Prolific:

        ::

            tags.div(
                tags.p("Thank you for participating in this experiment!"),
                tags.p("Please click the following URL to continue back to Prolific:"),
                tags.a("Finish experiment", href="https://prolific.com"),
            )
        """
        return "default_exit_message"

    @classmethod
    def extra_files(cls):
        files = []
        for trialmaker in cls.timeline.trial_makers.values():
            files.extend(trialmaker.extra_files())

        # Warning: Due to the behavior of Dallinger's extra_files functionality, files are NOT
        # overwritten if they exist already in Dallinger. We should try and change this.
        files.extend(
            [
                (
                    # Warning: this won't affect templates that already exist in Dallinger
                    resources.files("psynet") / "templates",
                    "/templates",
                ),
                (
                    resources.files("psynet") / "resources/favicon.png",
                    "/static/favicon.png",
                ),
                (
                    resources.files("psynet") / "resources/favicon.svg",
                    "/static/favicon.svg",
                ),
                (
                    resources.files("psynet") / "resources/logo.png",
                    "/static/images/logo.png",
                ),
                (
                    resources.files("psynet") / "resources/images/psynet.svg",
                    "/static/images/logo.svg",
                ),
                (
                    resources.files("psynet")
                    / "resources/images/princeton-consent.png",
                    "/static/images/princeton-consent.png",
                ),
                (
                    resources.files("psynet") / "resources/images/unity_logo.png",
                    "/static/images/unity_logo.png",
                ),
                (
                    resources.files("psynet")
                    / "resources/scripts/dashboard_timeline.js",
                    "/static/scripts/dashboard_timeline.js",
                ),
                (
                    resources.files("psynet")
                    / "resources/scripts/d3-visualizations.js",
                    "/static/scripts/d3-visualizations.js",
                ),
                (
                    resources.files("psynet")
                    / "resources/libraries/bootstrap/bootstrap.min.css",
                    "/static/css/bootstrap.min.css",
                ),
                (
                    resources.files("psynet")
                    / "resources/libraries/bootstrap/bootstrap.bundle.min.js",
                    "/static/scripts/bootstrap.bundle.min.js",
                ),
                (
                    resources.files("psynet")
                    / "resources/libraries/bootstrap-select/bootstrap-select.min.js",
                    "/static/scripts/bootstrap-select.min.js",
                ),
                (
                    resources.files("psynet")
                    / "resources/libraries/bootstrap-select/bootstrap-select.min.css",
                    "/static/css/bootstrap-select.min.css",
                ),
                (
                    resources.files("psynet") / "resources/css/consent.css",
                    "/static/css/consent.css",
                ),
                (
                    resources.files("psynet") / "resources/css/dashboard_timeline.css",
                    "/static/css/dashboard_timeline.css",
                ),
                (
                    resources.files("psynet")
                    / "resources/libraries/jQuery/jquery-3.7.1.min.js",
                    "/static/scripts/jquery-3.7.1.min.js",
                ),
                (
                    resources.files("psynet")
                    / "resources/libraries/platform-1.3.6/platform.min.js",
                    "/static/scripts/platform.min.js",
                ),
                (
                    resources.files("psynet")
                    / "resources/libraries/detectIncognito-1.3.0/detectIncognito.min.js",
                    "/static/scripts/detectIncognito.min.js",
                ),
                (
                    resources.files("psynet")
                    / "resources/libraries/raphael-2.3.0/raphael.min.js",
                    "/static/scripts/raphael-2.3.0.min.js",
                ),
                (
                    resources.files("psynet")
                    / "resources/libraries/jQuery-Knob/js/jquery.knob.js",
                    "/static/scripts/jquery.knob.js",
                ),
                (
                    resources.files("psynet") / "resources/libraries/js-synthesizer",
                    "/static/scripts/js-synthesizer",
                ),
                (
                    resources.files("psynet") / "resources/libraries/JSZip",
                    "/static/scripts/JSZip",
                ),
                (
                    resources.files("psynet") / "resources/libraries/Tonejs",
                    "/static/scripts/Tonejs",
                ),
                (
                    resources.files("psynet") / "resources/libraries/survey-jquery",
                    "/static/scripts/survey-jquery",
                ),
                (
                    resources.files("psynet") / "resources/libraries/abc-js",
                    "/static/scripts/abc-js",
                ),
                (
                    resources.files("psynet") / "resources/libraries/d3/d3.v4.js",
                    "/static/scripts/d3.v4.js",
                ),
                (
                    resources.files("psynet") / "resources/libraries/d3/d3-tip.min.js",
                    "/static/scripts/d3-tip.min.js",
                ),
                (
                    resources.files("psynet") / "resources/libraries/d3/d3-tip.css",
                    "/static/css/d3-tip.css",
                ),
                (
                    resources.files("psynet")
                    / "resources/libraries/jqueryui/jquery-ui.css",
                    "/static/css/jquery-ui.css",
                ),
                (
                    resources.files("psynet")
                    / "resources/libraries/jqueryui/jquery-ui.min.js",
                    "/static/scripts/jquery-ui.min.js",
                ),
                (
                    resources.files("psynet")
                    / "resources/libraries/international-keyboards",
                    "/static/international-keyboards",
                ),
                (
                    resources.files("psynet")
                    / "resources/scripts/prepare_docker_image.sh",
                    "prepare_docker_image.sh",
                ),
                (
                    resources.files("psynet") / "resources/DEPLOYMENT_PACKAGE",
                    "DEPLOYMENT_PACKAGE",
                ),
                (
                    "config.txt",
                    ".config.backup",
                ),
                (
                    ".deploy",
                    ".deploy",
                ),
                (
                    "source_code.zip",
                    "source_code.zip",
                ),
            ]
        )
        # We don't think this is needed any more but just keeping a note in case we're proved wrong (25 Sep 2023)
        # if isinstance(cls.assets.storage, DebugStorage):
        #     _path = f"static/{cls.assets.storage.label}"
        #     files.append(
        #         (
        #             _path,
        #             _path,
        #         )
        #     )
        return files

    @classmethod
    def extra_parameters(cls):
        config = dallinger_get_config()
        config.register("big_base_payment", bool)
        config.register("cap_recruiter_auth_token", unicode, sensitive=True)
        config.register("check_dallinger_version", bool)
        config.register("check_participant_opened_devtools", bool)
        config.register("currency", unicode)
        config.register("default_translator", unicode)
        config.register("enable_google_search_console", bool)
        config.register("google_translate_json_path", unicode, sensitive=True)
        config.register("google_translate_project_id", unicode, sensitive=True)
        config.register("initial_recruitment_size", int)
        config.register("openai_api_key", unicode, sensitive=True)
        config.register("openai_default_model", unicode)
        config.register("openai_default_temperature", unicode)
        config.register("label", unicode)
        config.register("locale", unicode)
        config.register("lucid_api_key", unicode, sensitive=True)
        config.register("lucid_recruitment_config", unicode)
        config.register("lucid_sha1_hashing_key", unicode, sensitive=True)
        config.register("min_accumulated_reward_for_abort", float)
        config.register("min_browser_version", unicode)
        config.register("show_abort_button", bool)
        config.register("show_footer", bool)
        config.register("show_progress_bar", bool)
        config.register("show_reward", bool)
        config.register("wage_per_hour", float)
        config.register("window_height", int)
        config.register("window_width", int)

        def is_valid_locale(value):
            from .translation import psynet_supported_locales

            locales = json.loads(value)
            if len(locales) == 0 or locales == ["en"]:
                return

            for locale in json.loads(value):
                if locale == "en":
                    continue
                assert (
                    locale in psynet_supported_locales
                ), f"Locale {locale} not available in PsyNet."

        config.register(
            "supported_locales", unicode, validators=[is_valid_json, is_valid_locale]
        )
        config.register("force_google_chrome", bool)
        config.register("force_incognito_mode", bool)
        config.register("allow_mobile_devices", bool)

        def color_mode_validator(value):
            assert value in ["light", "dark", "auto"]

        config.register("color_mode", unicode, validators=[color_mode_validator])

    @dashboard_tab("Export", after_route="database")
    @classmethod
    def dashboard_export(cls):
        return render_template(
            "dashboard_export.html",
            title="Database export",
        )

    @dashboard_tab("Timeline", after_route="monitoring")
    @classmethod
    def dashboard_timeline(cls):
        exp = get_experiment()
        panes = exp.monitoring_panels()

        module_info = {
            "modules": [{"id": module.id} for module in exp.timeline.module_list]
        }

        return render_template(
            "dashboard_timeline.html",
            title="Timeline modules",
            panes=panes,
            timeline_modules=json.dumps(module_info, default=serialise),
            currency=get_config().currency,
        )

    @dashboard_tab("Resources", after_route="monitoring")
    @classmethod
    def resources(cls):
        from .dashboard.resources import report_resource_use

        return report_resource_use()

    @dashboard_tab("Lucid", after_route="monitoring")
    @classmethod
    def lucid(cls):
        from .dashboard.lucid import report_lucid

        return report_lucid()

    @dashboard_tab("Participant", after_route="monitoring")
    @classmethod
    def participant(cls):
        message = ""
        participant = None

        assignment_id = request.args.get("assignment_id", default=None)
        participant_id = request.args.get("participant_id", default=None)
        worker_id = request.args.get("worker_id", default=None)

        try:
            if assignment_id is not None:
                participant = cls.get_participant_from_assignment_id(
                    assignment_id, for_update=False
                )
            elif participant_id is not None:
                participant = cls.get_participant_from_participant_id(
                    int(participant_id), for_update=False
                )
            elif worker_id is not None:
                participant = cls.get_participant_from_worker_id(
                    worker_id, for_update=False
                )
            else:
                message = "Please select a participant."
        except ValueError:
            message = "Invalid ID."
        except sqlalchemy.orm.exc.NoResultFound:
            message = "Failed to find any matching participants."
        except sqlalchemy.orm.exc.MultipleResultsFound:
            message = "Found multiple participants matching those specifications."

        return render_template(
            "participant.html",
            title="Participant",
            participant=participant,
            message=message,
            app_base_url=get_base_url(),
        )

    @classmethod
    def get_participant_from_assignment_id(
        cls, assignment_id: str, for_update: bool = False
    ):
        """
        Get a participant with a specified ``assignment_id``.
        Throws a ``sqlalchemy.orm.exc.NoResultFound`` error if there is no such participant,
        or a ``sqlalchemy.orm.exc.MultipleResultsFound`` error if there are multiple such participants.

        Parameters
        ----------
        assignment_id :
            ID of the participant to retrieve.

        for_update :
            Set to ``True`` if you plan to update this Participant object.
            The Participant object will be locked for update in the database
            and only released at the end of the transaction.

        Returns
        -------

        The corresponding participant object.
        """
        query = Participant.query.filter_by(assignment_id=assignment_id)
        if for_update:
            query = query.with_for_update(of=Participant).populate_existing()
        return query.one()

    @classmethod
    def get_participant_from_participant_id(
        cls, participant_id: int, for_update: bool = False
    ):
        """
        Get a participant with a specified ``participant_id``.
        Throws a ``ValueError`` if the ``participant_id`` is not a valid integer,
        a ``sqlalchemy.orm.exc.NoResultFound`` error if there is no such participant,
        or a ``sqlalchemy.orm.exc.MultipleResultsFound`` error if there are multiple such participants.

        Parameters
        ----------
        participant_id :
            ID of the participant to retrieve.

        for_update :
            Set to ``True`` if you plan to update this Participant object.
            The Participant object will be locked for update in the database
            and only released at the end of the transaction.

        Returns
        -------

        The corresponding participant object.
        """
        participant_id = int(participant_id)
        query = Participant.query.filter_by(id=participant_id)
        if for_update:
            query = query.with_for_update(of=Participant).populate_existing()
        return query.one()

    @classmethod
    def get_participant_from_worker_id(cls, worker_id: str, for_update: bool = False):
        """
        Get a participant with a specified ``worker_id``.
        Throws a ``sqlalchemy.orm.exc.NoResultFound`` error if there is no such participant,
        or a ``sqlalchemy.orm.exc.MultipleResultsFound`` error if there are multiple such participants.

        Parameters
        ----------
        worker_id :
            ID of the participant to retrieve.

        for_update :
            Set to ``True`` if you plan to update this Participant object.
            The Participant object will be locked for update in the database
            and only released at the end of the transaction.

        Returns
        -------

        The corresponding participant object.
        """
        query = Participant.query.filter_by(worker_id=worker_id)
        if for_update:
            query = query.with_for_update(of=Participant).populate_existing()
        return query.one()

    @classmethod
    def get_participant_from_unique_id(cls, unique_id: str, for_update: bool = False):
        """
        Get a participant with a specified ``unique_id``.
        Throws a ``sqlalchemy.orm.exc.NoResultFound`` error if there is no such participant,
        or a ``sqlalchemy.orm.exc.MultipleResultsFound`` error if there are multiple such participants.

        Parameters
        ----------
        unique_id :
            Unique ID of the participant to retrieve.

        for_update :
            Set to ``True`` if you plan to update this Participant object.
            The Participant object will be locked for update in the database
            and only released at the end of the transaction.

        Returns
        -------

        The corresponding participant object.
        """
        query = Participant.query.filter_by(unique_id=unique_id)
        if for_update:
            query = query.with_for_update(of=Participant).populate_existing()
        return query.one()

    @experiment_route("/google3580fca13e19b596.html")
    @staticmethod
    def google_search_console():
        """
        This route is disabled by default, but can be enabled by setting
        `enable_google_search_console = true` in config.txt.
        Enabling this route allows the site to be claimed in the Google Search Console
        dashboard of the computational.audition@gmail.com Google account.
        This allows the account to investigate and debug Chrome warnings
        (e.g. 'Deceptive website ahead'). See https://search.google.com/u/4/search-console.
        """
        if get_config().get("enable_google_search_console", default=False):
            return render_template("google3580fca13e19b596.html")
        else:
            return flask.Response(
                (
                    "Google search console verification is disabled, "
                    "you can activate it by setting enable_google_search_console = true in config.txt.",
                ),
                status=404,
            )

    @experiment_route("/ad", methods=["GET"])
    @nocache
    @staticmethod
    @with_transaction
    def advertisement():
        from dallinger.experiment_server.experiment_server import prepare_advertisement

        try:
            is_redirect, kw = prepare_advertisement()
            if is_redirect:
                return kw["redirect"]
            else:
                return render_template_with_translations("ad.html", **kw)
        except Exception as e:
            return Experiment.pre_timeline_error_page(e, request)

    @experiment_route("/consent")
    @staticmethod
    @with_transaction
    def consent():
        entry_information = request.args.to_dict()
        exp = get_experiment()
        entry_data = exp.normalize_entry_information(entry_information)

        hit_id = entry_data.get("hit_id")
        assignment_id = entry_data.get("assignment_id")
        worker_id = entry_data.get("worker_id")
        unique_id = worker_id + ":" + assignment_id
        try:
            return render_template_with_translations(
                "consent.html",
                hit_id=hit_id,
                assignment_id=assignment_id,
                worker_id=worker_id,
                unique_id=unique_id,
                mode=get_config().get("mode"),
                query_string=request.query_string.decode(),
            )
        except Exception as e:
            return Experiment.pre_timeline_error_page(e, request)

    @experiment_route("/start", methods=["GET"])
    @staticmethod
    @with_transaction
    def route_start():
        try:
            return render_template_with_translations("start.html")
        except Exception as e:
            return Experiment.pre_timeline_error_page(e, request)

    @staticmethod
    def pre_timeline_error_page(e, request):
        error_text = f"Error when calling {request.path} route: {e}"
        logger.error(error_text)
        exp = get_experiment()
        recruiter = exp.recruiter
        external_submit_url = None
        if isinstance(recruiter, (DevLucidRecruiter, LucidRecruiter)):
            rid = request.args.to_dict()["RID"]
            recruiter.set_termination_details(rid, error_text)
            external_submit_url = recruiter.external_submit_url(assignment_id=rid)
        return Experiment.error_page(
            recruiter=recruiter, external_submit_url=external_submit_url
        )

    @experiment_route("/app_deployment_id", methods=["GET"])
    @staticmethod
    def app_deployment_id():
        exp = get_experiment()
        return exp.deployment_id

    @experiment_route("/download_source", methods=["GET"])
    @classmethod
    def download_source(cls):
        config = get_config()

        if not authenticate(request.authorization, config):
            return jsonify({"message": "Invalid credentials"}), 401

        filename = "source_code.zip"
        logger.info(f"Downloading experiment source code from {os.getcwd()}/{filename}")
        return send_file(filename, mimetype="zip")

    @experiment_route("/dashboard/export", methods=["GET"])
    @staticmethod
    @with_transaction
    def export():
        from flask_login import current_user

        from .command_line import export__local

        config = get_config()

        if not current_user.is_authenticated and request.remote_addr != "127.0.0.1":
            return error_response(error_text="Invalid credentials", simple=True)

        with tempfile.TemporaryDirectory() as tempdir:
            ctx = Context(export__local)
            ctx.invoke(
                export__local,
                path=tempdir,
                n_parallel=None,
                username=config.get("dashboard_user"),
                password=config.get("dashboard_password"),
            )

            zip_filepath = shutil.make_archive(
                f'{config.get("label")}-data', "zip", tempdir
            )
            return send_file(zip_filepath, mimetype="zip")

    @experiment_route("/get_participant_info_for_debug_mode", methods=["GET"])
    @staticmethod
    @with_transaction
    def get_participant_info_for_debug_mode():
        if not get_config().get("mode") == "debug":
            return error_response()

        participant = Participant.query.first()
        json_data = {
            "id": participant.id,
            "unique_id": participant.unique_id,
            "assignment_id": participant.assignment_id,
            "page_uuid": participant.page_uuid,
        }
        logger.debug(
            f"Returning from /get_participant_info_for_debug_mode: {json_data}"
        )
        return json.dumps(json_data, default=serialise)

    @experiment_route("/on-demand-asset", methods=["GET"])
    @staticmethod
    def get_on_demand_asset():
        id = request.args.get("id")
        secret = request.args.get("secret")

        assert id
        assert secret

        id = int(id)

        asset = OnDemandAsset.query.filter_by(id=id).one()
        suffix = asset.extension if asset.extension else ""

        with tempfile.NamedTemporaryFile(suffix=suffix) as temp_file:
            asset.export(temp_file.name)

            return send_file(temp_file.name, max_age=0)

    @experiment_route("/error-page", methods=["POST", "GET"])
    @classmethod
    @with_transaction
    def render_error(cls):
        request_data = request.form.get("request_data")
        participant_id = request.form.get("participant_id")

        compensate = True
        participant = None
        recruiter = None
        external_submit_url = None

        if participant_id:
            participant = Participant.query.filter_by(id=participant_id).one()
            recruiter = get_experiment().recruiter
            external_submit_url = None
            if hasattr(recruiter, "external_submit_url"):
                external_submit_url = recruiter.external_submit_url(
                    participant=participant
                )

            if isinstance(recruiter, (DevLucidRecruiter, LucidRecruiter)):
                compensate = False
                recruiter.set_termination_details(
                    participant.assignment_id, "error-page_route"
                )

        return cls.error_page(
            participant=participant,
            request_data=request_data,
            recruiter=recruiter,
            external_submit_url=external_submit_url,
            compensate=compensate,
        )

    @experiment_route("/module", methods=["POST"])
    @classmethod
    @with_transaction
    def get_module_details_as_rendered_html(cls):
        exp = get_experiment()
        module = exp.timeline.get_module(request.values["moduleId"])
        return module.visualize()

    @experiment_route("/module/tooltip", methods=["POST"])
    @classmethod
    @with_transaction
    def get_module_tooltip_as_rendered_html(cls):
        exp = get_experiment()
        module = exp.timeline.get_module(request.values["moduleId"])
        return module.visualize_tooltip()

    @experiment_route("/module/progress_info", methods=["GET"])
    @classmethod
    @with_transaction
    def get_progress_info(cls):
        exp = get_experiment()
        module_ids = request.args.getlist("module_ids[]")
        return exp._get_progress_info(module_ids)

    def _get_progress_info(self, module_ids: list):
        progress_info = {
            "spending": {
                "amount_spent": self.amount_spent(),
                "currency": get_config().currency,
                "soft_max_experiment_payment": self.var.soft_max_experiment_payment,
                "hard_max_experiment_payment": self.var.hard_max_experiment_payment,
            }
        }

        participant_counts_by_module = self.get_participant_counts_by_module()

        for module_id in module_ids:
            module = self.timeline.modules[module_id]
            participant_counts = participant_counts_by_module[module_id]
            progress_info.update(
                module.get_progress_info(
                    participant_counts,
                )
            )

        return progress_info

    def get_participant_counts_by_module(self):
        counts = {module_id: {} for module_id in self.timeline.modules.keys()}

        for attr in ["started", "finished", "aborted"]:
            col = getattr(ModuleState, attr)
            rows = (
                db.session.query(
                    ModuleState.module_id, func.count(ModuleState.id).label("count")
                )
                .filter(col)
                .group_by(ModuleState.module_id)
            ).all()
            rows = dict(rows)

            for module_id in counts.keys():
                counts[module_id][attr] = rows.get(module_id, 0)

        return counts

    @experiment_route("/module/update_spending_limits", methods=["POST"])
    @classmethod
    @with_transaction
    def update_spending_limits(cls):
        hard_max_experiment_payment = request.values["hard_max_experiment_payment"]
        soft_max_experiment_payment = request.values["soft_max_experiment_payment"]
        exp = get_experiment()
        exp.var.set("hard_max_experiment_payment", float(hard_max_experiment_payment))
        exp.var.set("soft_max_experiment_payment", float(soft_max_experiment_payment))
        logger.info(
            f"Experiment variable 'hard_max_experiment_payment set' set to {hard_max_experiment_payment}."
        )
        logger.info(
            f"Experiment variable 'soft_max_experiment_payment set' set to {soft_max_experiment_payment}."
        )
        return success_response()

    @experiment_route("/debugger/<password>", methods=["GET"])
    @classmethod
    @with_transaction
    def route_debugger(cls, password):
        exp = get_experiment()
        if password == "my-secure-password-195762":
            exp.new(db.session)
            rpdb.set_trace()
            return success_response()
        return error_response()

    @experiment_route("/node/<int:node_id>/fail", methods=["GET", "POST"])
    @staticmethod
    @with_transaction
    def fail_node(node_id):
        from dallinger.models import Node

        node = Node.query.with_for_update(of=Node).populate_existing().get(node_id)
        node.fail(reason="http_fail_route_called")
        return success_response()

    @experiment_route("/info/<int:info_id>/fail", methods=["GET", "POST"])
    @staticmethod
    @with_transaction
    def fail_info(info_id):
        from dallinger.models import Info

        info = Info.query.with_for_update(of=Info).populate_existing().get(info_id)
        info.fail(reason="http_fail_route_called")
        return success_response()

    @experiment_route("/network/<int:network_id>/grow", methods=["GET", "POST"])
    @classmethod
    @with_transaction
    def grow_network(cls, network_id):
        exp = get_experiment()
        from .trial.main import TrialNetwork, TrialNode

        network = (
            TrialNetwork.query.with_for_update(of=[TrialNetwork, TrialNode])
            .populate_existing()
            .get(network_id)
        )
        trial_maker = exp.timeline.get_trial_maker(network.trial_maker_id)
        trial_maker.call_grow_network(network)
        return success_response()

    @experiment_route(
        "/network/<int:network_id>/call_async_post_grow_network",
        methods=["GET", "POST"],
    )
    @staticmethod
    @with_transaction
    def call_async_post_grow_network(network_id):
        from .trial.main import NetworkTrialMaker, TrialNetwork

        network = (
            TrialNetwork.query.with_for_update(of=TrialNetwork)
            .populate_existing()
            .get(network_id)
        )
        trial_maker = get_trial_maker(network.trial_maker_id)
        assert isinstance(trial_maker, NetworkTrialMaker)
        trial_maker.queue_async_post_grow_network(network)
        return success_response()

    # Lucid recruitment specific route
    @experiment_route("/terminate_participant", methods=["GET"])
    @classmethod
    @with_transaction
    def terminate_participant(cls):
        recruiter = get_experiment().recruiter
        participant = recruiter.get_participant(request)
        external_submit_url = recruiter.terminate_participant(
            participant=participant, reason=request.values.get("reason")
        )

        return render_template_with_translations(
            "exit_recruiter_lucid.html",
            external_submit_url=external_submit_url,
        )

    @experiment_route("/change_lucid_status", methods=["GET"])
    @classmethod
    def change_lucid_status(cls):
        get_experiment().recruiter.change_lucid_status(request.values.get("status", ""))
        return success_response()

    @staticmethod
    def get_client_ip_address():
        if request.environ.get("HTTP_X_FORWARDED_FOR") is None:
            return request.environ["REMOTE_ADDR"]
        else:
            return request.environ["HTTP_X_FORWARDED_FOR"]

    @experiment_route("/set_participant_as_aborted/<assignment_id>", methods=["GET"])
    @classmethod
    @with_transaction
    def route_set_participant_as_aborted(cls, assignment_id):  # TODO - update
        participant = cls.get_participant_from_assignment_id(
            assignment_id, for_update=True
        )
        participant.aborted = True
        if participant.module_state:
            participant.module_state.abort()
        logger.info(f"Aborted participant with ID '{participant.id}'.")
        return success_response()

    @experiment_route("/abort/<assignment_id>", methods=["GET"])
    @classmethod
    @with_transaction
    def route_abort(cls, assignment_id):
        try:
            template_name = "abort_not_possible.html"
            participant = None
            participant_abort_info = None
            if assignment_id is not None:
                participant = cls.get_participant_from_assignment_id(
                    assignment_id, for_update=False
                )
                if participant.calculate_reward() >= get_config().get(
                    "min_accumulated_reward_for_abort"
                ):
                    template_name = "abort_possible.html"
                    participant_abort_info = participant.abort_info()
        except ValueError:
            logger.error("Invalid assignment ID.")
        except sqlalchemy.orm.exc.NoResultFound:
            logger.error("Failed to find any matching participants.")
        except sqlalchemy.orm.exc.MultipleResultsFound:
            logger.error("Found multiple participants matching those specifications.")

        return render_template_with_translations(
            template_name,
            participant=participant,
            participant_abort_info=participant_abort_info,
        )

    @experiment_route("/timeline", methods=["GET"])
    @classmethod
    @with_transaction
    def route_timeline(cls):
        unique_id = request.args.get("unique_id")
        mode = request.args.get("mode")
        participant = cls.get_participant_from_unique_id(unique_id, for_update=False)
        experiment = get_experiment()

        return cls._route_timeline(experiment, participant, mode)

    @classmethod
    def fail_participant_on_error(cls, participant, error):
        error_type = str(type(error))
        # convert error type like <class 'Exception'> to 'Exception'
        error_type = error_type.split("'")[1]
        participant.failure_tags.append(error_type)
        participant.fail(error_type)

    @classmethod
    def _route_timeline(cls, experiment, participant, mode):
        try:
            if not isinstance(participant, Bot):
                participant.client_ip_address = cls.get_client_ip_address()
            page = cls.get_current_page(experiment, participant)
            return cls.serialize_page(page, experiment, participant, mode)
        except cls.HandledError as err:
            return err.error_page()
        except Exception as err:
            if os.getenv("PASSTHROUGH_ERRORS"):
                raise
            handled_error = cls.handle_error(
                err,
                participant=participant,
                trial=participant.current_trial,
                node=(
                    participant.current_trial.node
                    if participant.current_trial
                    else None
                ),
                network=(
                    participant.current_trial.network
                    if participant.current_trial
                    else None
                ),
            )
            cls.fail_participant_on_error(participant, err)
            return handled_error.error_page()

    @classmethod
    def handle_error(cls, error, **kwargs):
        parents = cls._compile_error_parents(**kwargs)
        cls.report_error(error, **parents)
        return cls.HandledError(**parents)

    @staticmethod
    def _compile_error_parents(**kwargs):
        parents = {**kwargs}
        types = [
            "process",
            "asset",
            "response",
            "trial",
            "node",
            "network",
            "participant",
        ]
        for i, parent_type in enumerate(types):
            if parent_type in parents:
                parent = parents[parent_type]
                for grandparent_type in types[(i + 1) :]:
                    if (
                        grandparent_type not in parents
                        and hasattr(parent, grandparent_type)
                        and getattr(parent, grandparent_type) is not None
                    ):
                        parents[grandparent_type] = getattr(parent, grandparent_type)
        return parents

    class HandledError(Exception):
        def __init__(self, message=None, participant=None, **kwargs):
            super().__init__(message)
            self.participant = participant

        def error_page(self):
            return Experiment.error_page(self.participant)

    @classmethod
    def report_error(
        cls,
        error,
        **kwargs,
    ):
        token = cls.generate_error_token()
        cls.log_to_stdout(error, token, **kwargs)
        cls.log_to_db(error, token, **kwargs)

    @classmethod
    def generate_error_token(cls):
        return str(uuid.uuid4())[:8]

    @classmethod
    def log_to_stdout(cls, error, token, **kwargs):
        _ = error
        context = cls.serialize_error_context(**kwargs)
        print("\n")
        logger.error(
            "EXPERIMENT ERROR - err-%s:%s",
            token,
            context,
            exc_info=True,
        )
        print("\n")

    @classmethod
    def log_to_db(cls, error, token, **kwargs):
        trace = traceback.format_exc()
        record = ErrorRecord(error=error, traceback=trace, token=token, **kwargs)
        db.session.add(record)
        db.session.commit()

    @classmethod
    def serialize_error_context(
        cls,
        participant=None,
        response=None,
        trial=None,
        node=None,
        network=None,
        process=None,
        asset=None,
    ):
        context = {}
        if participant:
            context["participant_id"] = participant.id
            context["worker_id"] = participant.worker_id
        if response:
            context["response_id"] = response.id
        if trial:
            context["trial_id"] = trial.id
        if node:
            context["node_id"] = node.id
        if network:
            context["network_id"] = network.id
        if process:
            context["process_id"] = process.id
        if asset:
            context["asset_id"] = asset.id
        return context

    class UniqueIdError(PermissionError):
        def __init__(self, expected, provided, participant):
            self.participant = participant

            message = "".join(
                [
                    f"Mismatch between expected unique_id ({expected}) "
                    f"and provided unique_id ({provided}) "
                    f"for participant {participant.id}."
                ]
            )
            super().__init__(message)

        def http_response(self):
            last_exception = sys.exc_info()
            if last_exception[0]:
                logger.error(
                    "Failure for request: {!r}".format(dict(request.args)),
                    exc_info=last_exception,
                )

            msg = (
                "There was a problem authenticating your session, "
                + "did you switch browsers? Unfortunately this is not currently "
                + "supported by our system."
            )
            return Experiment.error_page(
                participant=self.participant,
                error_text=msg,
                error_type="authentication",
            )

    @classmethod
    @log_time_taken
    def get_current_page(cls, experiment, participant):
        if participant.elt_id == [-1]:
            experiment.timeline.advance_page(experiment, participant)

        page = experiment.timeline.get_current_elt(experiment, participant)
        page.pre_render()

        return page

    @classmethod
    def serialize_page(cls, page, experiment, participant, mode):
        if mode == "json":
            return jsonify(page.__json__(participant))
        else:
            return page.render(experiment, participant)

    @classmethod
    def check_unique_id(cls, participant, unique_id):
        valid = participant.unique_id == unique_id
        if not valid:
            raise cls.UniqueIdError(
                expected=unique_id,
                provided=participant.unique_id,
                participant=participant,
            )
        else:
            return True

    @experiment_route("/timeline/progress_and_reward", methods=["GET"])
    @classmethod
    @with_transaction
    def get_progress_and_reward(cls):
        participant_id = request.args.get("participantId")
        participant = Participant.query.get(participant_id)
        progress_percentage = round(participant.progress * 100)
        data = {
            "progressPercentage": progress_percentage,
            "progressPercentageStr": f"{progress_percentage}%",
        }
        if get_config().get("show_reward"):
            time_reward = participant.time_reward
            performance_reward = participant.performance_reward
            total_reward = participant.calculate_reward()
            data["reward"] = {
                "time": time_reward,
                "performance": performance_reward,
                "total": total_reward,
            }
        return data

    @experiment_route("/response", methods=["POST"])
    @classmethod
    @with_transaction
    def route_response(cls):
        exp = get_experiment()
        json_data = json.loads(request.values["json"])
        blobs = request.files.to_dict()

        participant_id = get_arg_from_dict(json_data, "participant_id")
        page_uuid = get_arg_from_dict(json_data, "page_uuid")
        raw_answer = get_arg_from_dict(
            json_data, "raw_answer", use_default=True, default=None
        )
        metadata = get_arg_from_dict(json_data, "metadata")
        client_ip_address = cls.get_client_ip_address()

        res = exp.process_response(
            participant_id,
            raw_answer,
            blobs,
            metadata,
            page_uuid,
            client_ip_address,
        )

        return res

    @experiment_route("/log/<level>/<unique_id>", methods=["POST"])
    @classmethod
    @with_transaction
    def http_log(cls, level, unique_id):
        participant = cls.get_participant_from_unique_id(unique_id, for_update=False)
        try:
            cls.check_unique_id(participant, unique_id)
        except cls.UniqueIdError as e:
            return e.http_response()

        message = request.values["message"]

        assert level in ["warning", "info", "error"]

        string = f"[CLIENT {participant.id}]: {message}"

        if level == "info":
            logger.info(string)
        elif level == "warning":
            logger.warning(string)
        elif level == "error":
            logger.error(string)
        else:
            raise RuntimeError("This shouldn't happen.")

        return success_response()

    @staticmethod
    def extra_routes():
        raise RuntimeError(
            "\n\n"
            + "Due to a recent update, the following line is no longer required in PsyNet experiments:\n\n"
            + "extra_routes = Exp().extra_routes()\n\n"
            + "Please delete it from your experiment.py file and try again.\n"
        )

    @experiment_route(
        "/participant_opened_devtools/<unique_id>",
        methods=["POST"],
    )
    @classmethod
    @with_transaction
    def participant_opened_devtools(cls, unique_id):
        participant = cls.get_participant_from_unique_id(unique_id, for_update=False)

        cls.check_unique_id(participant, unique_id)

        participant.var.opened_devtools = True

        return success_response()

    def monitoring_statistics(self, **kwarg):
        stats = super().monitoring_statistics(**kwarg)

        del stats["Infos"]

        stats["Trials"] = OrderedDict(
            (
                ("count", Trial.query.count()),
                ("failed", Trial.query.filter_by(failed=True).count()),
            )
        )

        return stats

    def check_consents(self):
        if (
            deployment_info.read("is_local_deployment")
            and deployment_info.read("mode") == "debug"
        ):
            return
        self.timeline.check_consents(self)


Experiment.SuccessfulEndLogic = SuccessfulEndLogic
Experiment.UnsuccessfulEndLogic = UnsuccessfulEndLogic
Experiment.RejectedConsentLogic = RejectedConsentLogic


@register_table
class ExperimentConfig(SQLBase, SQLMixin):
    """
    This SQL-backed class provides a way to store experiment configuration variables
    that can change over the course of the experiment.
    See :class:`psynet.experiment.Experiment` documentation for example usage.
    """

    __tablename__ = "experiment"

    # Removing these fields because they don't make much sense for the experiment configuration object
    creation_time = None
    failed = None
    failed_reason = None
    time_of_death = None

    global_assets = relationship("Asset")
    global_nodes = relationship("psynet.trial.main.TrialNode")


def _patch_dallinger_models():
    # There are some Dallinger functions that rely on the ability to look up
    # models by name in dallinger.models. One example is the code for
    # generating dashboard tabs for SQL object types. We therefore need
    # to patch in certain PsyNet classes so that Dallinger can access them.
    dallinger.models.Trial = Trial
    dallinger.models.Response = Response


_patch_dallinger_models()


def import_local_experiment():
    # Imports experiment.py and returns a dict consisting of
    # 'package' which corresponds to the experiment *package*,
    # 'module' which corresponds to the experiment *module*, and
    # 'class' which corresponds to the experiment *class*.
    # It also adds the experiment directory to sys.path, meaning that any other
    # modules defined there can be imported using ``import``.
    # import pdb; pdb.set_trace()
    #
    # TODO - Is it a problem if we try to import_local_experiment before config.load() has been called?
    dallinger_get_config()

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
        "class": dallinger.experiment.load(),  # TODO - use the class as loaded above instead?
    }


@cache
def get_experiment() -> Experiment:
    """
    Returns an initialized instance of the experiment class.
    """
    return import_local_experiment()["class"](db.session)


@cache
def get_trial_maker(trial_maker_id) -> TrialMaker:
    exp = get_experiment()
    return exp.timeline.get_trial_maker(trial_maker_id)


def assert_config_txt_does_not_contain_sensitive_values():
    config = get_config()
    with open("config.txt", "r") as f:
        for line in f.readlines():
            for var in config.sensitive:
                if var in line:
                    raise ValueError(
                        f"Sensitive key '{var}' found in config.txt. Please move all sensitive "
                        "keys to `.dallingerconfig` and try again."
                    )


def in_deployment_package():
    return bool(os.getenv("DEPLOYMENT_PACKAGE") or os.path.exists("DEPLOYMENT_PACKAGE"))


def authenticate(auth, config):
    return (
        auth
        and auth.username == config.get("dashboard_user")
        and auth.password == config.get("dashboard_password")
    )


# Dallinger defines various HTTP routes that provide access to database content.
# We disable the following HTTP routes in PsyNet experiments because they could
# in theory leak personal data or be used to manipulate the state of the
# experiment. Most data should instead be transferred via authenticated PsyNet routes.
_protected_routes = [
    "/network/<network_id>",
    "/question/<participant_id>",
    "/node/<int:node_id>/neighbors",
    "/node/<participant_id>",
    "/node/<int:node_id>/vectors",
    "/node/<int:node_id>/connect/<int:other_node_id>",
    "/info/<int:node_id>/<int:info_id>",
    "/node/<int:node_id>/infos",
    "/node/<int:node_id>/received_infos",
    "/tracking_event/<int:node_id>",
    "/info/<int:node_id>",
    "/node/<int:node_id>/transmissions",
    "/node/<int:node_id>/transmit",
    "/node/<int:node_id>/transformations",
    "/transformation/<int:node_id>/<int:info_in_id>/<int:info_out_id>",
]
