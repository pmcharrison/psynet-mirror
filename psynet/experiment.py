import configparser
import json
import os
import shutil
import sys
import tempfile
import traceback
import uuid
from collections import OrderedDict
from datetime import datetime
from importlib import resources
from os.path import exists
from platform import python_version
from smtplib import SMTPAuthenticationError
from typing import List

import dallinger.experiment
import dallinger.models
import flask
import rpdb
import sqlalchemy.orm.exc
from click import Context
from dallinger import db
from dallinger.command_line import __version__ as dallinger_version
from dallinger.compat import unicode
from dallinger.config import get_config, is_valid_json
from dallinger.experiment import experiment_route, scheduled_task
from dallinger.experiment_server.dashboard import dashboard_tab
from dallinger.experiment_server.utils import nocache, success_response
from dallinger.notifications import admin_notifier
from dallinger.recruiters import MTurkRecruiter, ProlificRecruiter
from dallinger.utils import get_base_url
from dominate import tags
from flask import jsonify, render_template, request, send_file

from psynet import __version__

from . import deployment_info
from .asset import Asset, AssetRegistry, DebugStorage, FastFunctionAsset, NoStorage
from .bot import Bot
from .command_line import export_launch_data, log
from .data import SQLBase, SQLMixin, ingest_zip, register_table
from .error import ErrorRecord
from .field import ImmutableVarStore
from .graphics import PsyNetLogo
from .internationalization import check_translations, compile_mo, create_pot, load_po
from .page import InfoPage, SuccessfulEndPage
from .participant import Participant, get_participant
from .process import WorkerAsyncProcess
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
    ParticipantFailRoutine,
    PreDeployRoutine,
    RecruitmentCriterion,
    Response,
    Timeline,
)
from .trial.main import Trial, TrialMaker
from .trial.record import (  # noqa -- this is to make sure the SQLAlchemy class is registered
    Recording,
)
from .utils import (
    LOCALES_DIR,
    NoArgumentProvided,
    cache,
    call_function,
    call_function_with_context,
    classproperty,
    disable_logger,
    get_arg_from_dict,
    get_available_locales,
    get_language,
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


def get_and_load_config():
    config = get_config()
    if not config.ready:
        config.load()
    return config


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


class Experiment(dallinger.experiment.Experiment, metaclass=ExperimentMeta):
    # pylint: disable=abstract-method
    """
    The main experiment class from which to inherit when building experiments.

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
        (incl. bonuses) in US dollars exceedes this value. Default: `1000.0`.

    hard_max_experiment_payment : `float`
        Guarantees that in an experiment no more is spent than the value assigned.
        Bonuses are not paid from the point this value is reached and a record of the amount
        of unpaid bonus is kept in the participant's `unpaid_bonus` variable. Default: `1100.0`.

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

    min_accumulated_bonus_for_abort : `float`
        The threshold of bonus accumulated in US dollars for the participant to be able to receive
        compensation when aborting an experiment using the `Abort experiment` button. Default: `0.20`.

    show_abort_button : `bool`
        If ``True``, the `Ad` page displays an `Abort` button the participant can click to terminate the HIT,
        e.g. in case of an error where the participant is unable to finish the experiment. Clicking the button
        assures the participant is compensated on the basis of the amount of bonus that has been accumulated.
        Default ``False``.

    show_bonus : `bool`
        If ``True`` (default), then the participant's current estimated bonus is displayed
        at the bottom of the page.

    show_footer : `bool`
        If ``True`` (default), then a footer is displayed at the bottom of the page containing a 'Help' button
        and bonus information if `show_bonus` is set to `True`.

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

    allow_switching_locale : ``bool``
        Allow the user to change the language of the experiment during the experiment.
        Default: ``False``.

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

    initial_recruitment_size = INITIAL_RECRUITMENT_SIZE
    logos = []

    timeline = Timeline(
        InfoPage("Placeholder timeline", time_estimate=5), SuccessfulEndPage()
    )

    asset_storage = NoStorage()

    __extra_vars__ = {}

    variables = {}

    def __init__(self, session=None):
        super(Experiment, self).__init__(session)

        config_initial_recruitment_size = self.get_initial_recruitment_size()
        initial_recruitment_size_config_changed = (
            config_initial_recruitment_size != INITIAL_RECRUITMENT_SIZE
        )
        initial_recruitment_size_experiment_changed = (
            self.__class__.initial_recruitment_size != INITIAL_RECRUITMENT_SIZE
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

        locales_dir = os.path.abspath("locales")

        self.pre_deploy_routines = []
        if self.translation_checks_needed(locales_dir):
            self.pre_deploy_routines.append(
                PreDeployRoutine(
                    "check_experiment_translations",
                    check_translations,
                    {
                        "module": "experiment",
                        "locales_dir": locales_dir,
                        "variable_placeholders": self.variable_placeholders,
                        "create_translation_template_function": self._create_translation_template_from_experiment_folder,
                    },
                )
            )

        self.pre_deploy_routines.append(
            PreDeployRoutine(
                "compile_translations_if_necessary",
                self.compile_translations_if_necessary,
                {
                    "locales_dir": os.path.abspath("locales"),
                    "module": "experiment",
                },
            )
        )

        self.process_timeline()

    def translation_checks_needed(self, locales_dir):
        return (
            os.path.exists(locales_dir) and len(get_available_locales(locales_dir)) > 0
        )

    @classmethod
    def create_translation_template_from_experiment_folder(
        cls, input_directory, pot_path
    ):
        create_pot(input_directory, ".", pot_path, start_with_fresh_file=True)

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

    def compile_translations_if_necessary(self, locales_dir, module):
        """Compiles translations if necessary."""
        supported_locales = self.config.get("supported_locales", [])
        if self.translation_checks_needed(locales_dir):
            locales = get_available_locales(locales_dir)
            for locale in supported_locales:
                if locale == "en":
                    continue
                assert (
                    locale in locales
                ), f"Locale {locale} is not found in {locales_dir}"
                po_path = os.path.join(
                    locales_dir, locale, "LC_MESSAGES", module + ".po"
                )
                compile_mo(po_path)
        else:
            assert supported_locales == [], "No locales folder found"

    def compile_psynet_translations_if_necessary(self):
        self.compile_translations_if_necessary(LOCALES_DIR, "psynet")

    def on_launch(self):
        logger.info("Calling Exp.on_launch()...")
        self.compile_psynet_translations_if_necessary()
        redis_vars.set("launch_started", True)
        super().on_launch()
        if not deployment_info.read("redeploying_from_archive"):
            self.on_first_launch()
        self.timeline.verify_consents(self)
        self.on_every_launch()
        self.var.launch_finished = True
        logger.info("Experiment launch complete!")
        db.session.commit()
        redis_vars.set("launch_finished", True)

    def on_first_launch(self):
        logger.info("Calling Exp.on_first_launch()...")

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

        config = get_config()
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
        self.grow_all_networks()

    def load_deployment_config(self):
        config = get_config()
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

        for node in TrialNode.query.filter_by(_on_deploy_called=False).all():
            node.on_deploy()

        db.session.commit()

    def create_participant(self, **kwargs):
        assignment_id = kwargs["assignment_id"]
        if Participant.query.filter_by(assignment_id=assignment_id).count() > 0:
            raise ValueError(
                f"The assignment_id '{assignment_id}' already exists in the database."
            )
        return super().create_participant(**kwargs)

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

    def test_experiment(self):
        os.environ["PASSTHROUGH_ERRORS"] = "True"
        os.environ["DEPLOYMENT_PACKAGE"] = "True"
        bots = self.test_create_bots()
        self.test_run_bots(bots)
        self.test_check_bots(bots)

    def test_create_bots(self):
        return [Bot() for _ in range(self.test_n_bots)]

    def test_run_bots(self, bots):
        for bot in bots:
            db.session.add(bot)  # Protects against DetachedInstanceErrors
            self.run_bot(bot)

    def run_bot(self, bot):
        bot.take_experiment(render_pages=True)

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

        config = get_config()
        _, _p = get_translator(locale)
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
                contact_address=config.get("contact_email_on_error"),
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
        try:
            from psynet.participant import Participant

            participant = Participant.query.filter_by(worker_id=worker_id).one()
            locale = participant.var.locale
        except Exception:
            locale = None
        gettext, pgettext = get_translator(locale)
        _, _p = gettext, pgettext

        if hasattr(self.recruiter, "error_page_content"):
            return self.recruiter.error_page_content(
                gettext,
                pgettext,
                assignment_id=assignment_id,
                external_submit_url=external_submit_url,
            )

        # TODO: Refactor this so that the error page content generation is deferred to the recruiter class.
        if isinstance(self.recruiter, ProlificRecruiter):
            return self.error_page_content__prolific(gettext, pgettext)
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

    def error_page_content__prolific(self, _, _p):
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
    def check_database():
        exp = get_experiment()
        for c in exp.database_checks:
            c.run()

    @scheduled_task("interval", minutes=1, max_instances=1)
    @staticmethod
    def run_recruiter_checks():
        exp = get_experiment()
        recruiter = exp.recruiter
        if hasattr(recruiter, "run_checks"):
            recruiter.run_checks()

    @property
    def base_payment(self):
        return get_config().get("base_payment")

    @property
    def variable_placeholders(self):
        return {}

    def get_initial_recruitment_size(self):
        return get_and_load_config().get("initial_recruitment_size")

    @property
    def label(self):
        return get_and_load_config().get("label")

    @property
    def var(self):
        if self.experiment_config_exists:
            return self.experiment_config.var
        else:
            return ImmutableVarStore(self.variables_initial_values)

    @property
    def experiment_config(self):
        return ExperimentConfig.query.one()

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
    def estimated_max_bonus(cls, wage_per_hour):
        return cls.timeline.estimated_max_bonus(wage_per_hour)

    @classmethod
    def estimated_completion_time(cls, wage_per_hour):
        return cls.timeline.estimated_completion_time(wage_per_hour)

    @property
    def experiment_config_exists(self):
        return ExperimentConfig.query.count() > 0

    def setup_experiment_config(self):
        if not self.experiment_config_exists:
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
            "host": "0.0.0.0",
            "base_payment": 0.10,
            "clock_on": True,
            "duration": 100000000.0,
            "disable_when_duration_exceeded": False,
            "docker_volumes": "${HOME}/psynet-data/assets:/psynet-data/assets",
            "protected_routes": json.dumps(_protected_routes),
            "initial_recruitment_size": INITIAL_RECRUITMENT_SIZE,
            "label": cls.get_experiment_folder_name(),
            "min_browser_version": "80.0",
            "wage_per_hour": 9.0,
            "currency": "$",
            "min_accumulated_bonus_for_abort": 0.20,
            "show_abort_button": False,
            "show_bonus": True,
            "show_footer": True,
            "show_progress_bar": True,
            "check_participant_opened_devtools": False,
            "window_width": 1024,
            "window_height": 768,
            "supported_locales": "[]",
            "allow_switching_locale": True,
            "force_google_chrome": True,
            "force_incognito_mode": False,
            "allow_mobile_devices": False,
            "color_mode": "light",
            **cls.config,
        }

        config_types = get_config().types

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
            "launch_finished": False,
            "hard_max_experiment_payment_email_sent": False,
            "soft_max_experiment_payment_email_sent": False,
            "current_locale": get_language(),
            "hard_max_experiment_payment": 1100.0,
            "soft_max_experiment_payment": 1000.0,
            "max_participant_payment": 25.0,
        }

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
        config = get_config()
        return config.get("description")

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
                you should receive a bonus of approximately
                <span style="font-weight: bold;">${'{:.2f}'.format(self.estimated_bonus_in_dollars)}</span> depending on the
                amount of work done.
                <br>
                In some cases, the experiment may finish early: this is not an error, and there is no need to write to us.
                <br>
                In this case you will be paid in proportion to the amount of the experiment that you completed.
                """

    @property
    def variables_initial_values(self):
        config = get_and_load_config()

        for key, value in self.variables.items():
            assert key not in list(config.as_dict().keys()), (
                f"Variable {key} is a config variable and should solely be specified in the config.txt or in "
                "experiment.config but NOT as experiment variable."
            )
        return {**self._default_variables, **self.variables}

    @property
    def estimated_duration_in_minutes(self):
        return self.timeline.estimated_time_credit.get_max(mode="time") / 60

    @property
    def estimated_bonus_in_dollars(self):
        wage_per_hour = get_and_load_config().get("wage_per_hour")
        return round(
            self.timeline.estimated_time_credit.get_max(
                mode="bonus",
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

    def grow_all_networks(self):
        from .trial.main import NetworkTrialMaker

        NetworkTrialMaker.grow_all_networks(experiment=self)

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
    def check_config(cls):
        config = get_config()
        if not config.ready:
            config.load()

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

    def fail_participant(self, participant):
        logger.info(
            "Failing participant %i (%i routine(s) found)...",
            participant.id,
            len(self.participant_fail_routines),
        )
        participant.failed = True
        participant.time_of_death = datetime.now()
        for i, routine in enumerate(self.participant_fail_routines):
            logger.info(
                "Executing fail routine %i/%i ('%s')...",
                i + 1,
                len(self.participant_fail_routines),
                routine.label,
            )
            call_function(
                routine.function,
                participant=participant,
                experiment=self,
                assets=self.assets,
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
        Calculates and returns the bonus payment the given participant gets when
        completing the experiment. Override :func:`~psynet.experiment.Experiment.calculate_bonus()` if you require another than the default bonus calculation.

        :param participant:
            The participant.
        :type participant:
            :attr:`~psynet.participant.Participant`
        :returns:
            The bonus payment as a ``float``.
        """
        bonus = participant.calculate_bonus()
        return self.check_bonus(bonus, participant)

    def check_bonus(self, bonus, participant):
        """
        Ensures that a participant receives no more than a bonus of max_participant_payment.
        Additionally, checks if both soft_max_experiment_payment or max_participant_payment have
        been reached or exceeded, respectively. Emails are sent out warning the user if either is true.

        :param bonus: float
            The bonus calculated in :func:`~psynet.experiment.Experiment.calculate_bonus()`.
        :type participant:
            :attr: `~psynet.participant.Participant`
        :returns:
            The possibly reduced bonus as a ``float``.
        """

        # check hard_max_experiment_payment
        if (
            self.var.hard_max_experiment_payment_email_sent
            or self.amount_spent() + self.outstanding_base_payments() + bonus
            > self.var.hard_max_experiment_payment
        ):
            participant.var.set("unpaid_bonus", bonus)
            self.ensure_hard_max_experiment_payment_email_sent()

        # check soft_max_experiment_payment
        if self.amount_spent() + bonus >= self.var.soft_max_experiment_payment:
            self.ensure_soft_max_experiment_payment_email_sent()

        # check max_participant_payment
        if participant.amount_paid() + bonus > self.var.max_participant_payment:
            reduced_bonus = round(
                self.var.max_participant_payment - participant.amount_paid(), 2
            )
            participant.send_email_max_payment_reached(self, bonus, reduced_bonus)
            return reduced_bonus
        return bonus

    def outstanding_base_payments(self):
        return self.num_working_participants * self.base_payment

    def with_lucid_recruitment(self):
        return issubclass(self.recruiter.__class__, BaseLucidRecruiter)

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
        participant = get_participant(participant_id)

        if page_uuid != participant.page_uuid:
            logger.warn(
                f"Participant {participant_id} tried to submit data with the wrong page_uuid"
                + f"(submitted = {page_uuid}, required = {participant.page_uuid})."
            )
            return error_response()

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
                response, experiment=self, participant=participant
            )
            if isinstance(validation, FailedValidation):
                return self.response_rejected(message=validation.message)
            participant.time_credit.increment(event.time_estimate)
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
                    node=participant.current_trial.node
                    if participant.current_trial
                    else None,
                    network=participant.current_trial.network
                    if participant.current_trial
                    else None,
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
        # Warning: Due to the behavior of Dallinger's extra_files functionality, files are NOT
        # overwritten if they exist already in Dallinger. We should try and change this.
        files = [
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
                resources.files("psynet") / "resources/images/princeton-consent.png",
                "/static/images/princeton-consent.png",
            ),
            (
                resources.files("psynet") / "resources/images/unity_logo.png",
                "/static/images/unity_logo.png",
            ),
            (
                resources.files("psynet") / "resources/scripts/dashboard_timeline.js",
                "/static/scripts/dashboard_timeline.js",
            ),
            (
                resources.files("psynet") / "resources/css/bootstrap.min.css",
                "/static/css/bootstrap.min.css",
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
                / "resources/libraries/jQuery/jquery-3.6.0.min.js",
                "/static/scripts/jquery-3.6.0.min.js",
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
                resources.files("psynet") / "resources/scripts/prepare_docker_image.sh",
                "prepare_docker_image.sh",
            ),
            (
                ".deploy",
                ".deploy",
            ),
            (
                resources.files("psynet") / "resources/DEPLOYMENT_PACKAGE",
                "DEPLOYMENT_PACKAGE",
            ),
        ]
        if isinstance(cls.assets.storage, DebugStorage):
            _path = f"static/{cls.assets.storage.label}"
            files.append(
                (
                    _path,
                    _path,
                )
            )
        return files

    @classmethod
    def extra_parameters(cls):
        config = get_config()
        config.register("cap_recruiter_auth_token", unicode)
        config.register("lucid_api_key", unicode)
        config.register("lucid_sha1_hashing_key", unicode)
        config.register("lucid_recruitment_config", unicode)
        config.register("debug_storage_root", unicode)
        config.register("default_export_root", unicode)
        config.register("enable_google_search_console", bool)
        config.register("initial_recruitment_size", int)
        config.register("label", unicode)
        config.register("min_browser_version", unicode)
        config.register("wage_per_hour", float)
        config.register("currency", unicode)
        config.register("min_accumulated_bonus_for_abort", float)
        config.register("show_abort_button", bool)
        config.register("show_bonus", bool)
        config.register("show_footer", bool)
        config.register("show_progress_bar", bool)
        config.register("check_participant_opened_devtools", bool)
        config.register("window_width", int)
        config.register("window_height", int)

        def is_valid_locale(value):
            available_psynet_locales = get_available_locales()
            for locale in json.loads(value):
                if locale == "en":
                    continue
                assert (
                    locale in available_psynet_locales
                ), f"Locale {locale} not available in PsyNet."

        config.register(
            "supported_locales", unicode, validators=[is_valid_json, is_valid_locale]
        )
        config.register("allow_switching_locale", bool)
        config.register("force_google_chrome", bool)
        config.register("force_incognito_mode", bool)
        config.register("allow_mobile_devices", bool)

        def color_mode_validator(value):
            assert value in ["light", "dark", "auto"]

        config.register("color_mode", unicode, validators=[color_mode_validator])
        # config.register("keep_old_chrome_windows_in_debug_mode", bool)

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
        config = get_config()

        module_info = {
            "modules": [{"id": module.id} for module in exp.timeline.module_list]
        }

        return render_template(
            "dashboard_timeline.html",
            title="Timeline modules",
            panes=panes,
            timeline_modules=json.dumps(module_info, default=serialise),
            currency=config.currency,
        )

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
                participant = cls.get_participant_from_assignment_id(assignment_id)
            elif participant_id is not None:
                participant = cls.get_participant_from_participant_id(participant_id)
            elif worker_id is not None:
                participant = cls.get_participant_from_worker_id(worker_id)
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
    def get_participant_from_assignment_id(cls, assignment_id):
        """
        Get a participant with a specified ``assignment_id``.
        Throws a ``sqlalchemy.orm.exc.NoResultFound`` error if there is no such participant,
        or a ``sqlalchemy.orm.exc.MultipleResultsFound`` error if there are multiple such participants.

        Parameters
        ----------
        assignment_id :
            ID of the participant to retrieve.

        Returns
        -------

        The corresponding participant object.
        """
        return Participant.query.filter_by(assignment_id=assignment_id).one()

    @classmethod
    def get_participant_from_participant_id(cls, participant_id):
        """
        Get a participant with a specified ``participant_id``.
        Throws a ``ValueError`` if the ``participant_id`` is not a valid integer,
        a ``sqlalchemy.orm.exc.NoResultFound`` error if there is no such participant,
        or a ``sqlalchemy.orm.exc.MultipleResultsFound`` error if there are multiple such participants.

        Parameters
        ----------
        participant_id :
            ID of the participant to retrieve.

        Returns
        -------

        The corresponding participant object.
        """
        _id = int(participant_id)
        return Participant.query.filter_by(id=_id).one()

    @classmethod
    def get_participant_from_worker_id(cls, worker_id):
        """
        Get a participant with a specified ``worker_id``.
        Throws a ``sqlalchemy.orm.exc.NoResultFound`` error if there is no such participant,
        or a ``sqlalchemy.orm.exc.MultipleResultsFound`` error if there are multiple such participants.

        Parameters
        ----------
        worker_id :
            ID of the participant to retrieve.

        Returns
        -------

        The corresponding participant object.
        """
        return Participant.query.filter_by(worker_id=worker_id).one()

    @classmethod
    def get_participant_from_unique_id(cls, unique_id):
        """
        Get a participant with a specified ``unique_id``.
        Throws a ``sqlalchemy.orm.exc.NoResultFound`` error if there is no such participant,
        or a ``sqlalchemy.orm.exc.MultipleResultsFound`` error if there are multiple such participants.

        Parameters
        ----------
        unique_id :
            Unique ID of the participant to retrieve.

        Returns
        -------

        The corresponding participant object.
        """
        return Participant.query.filter_by(unique_id=unique_id).one()

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
        config = get_config()
        if config.get("enable_google_search_console", default=False):
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
    def consent():
        config = get_config()

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
                mode=config.get("mode"),
                query_string=request.query_string.decode(),
            )
        except Exception as e:
            return Experiment.pre_timeline_error_page(e, request)

    @experiment_route("/start", methods=["GET"])
    @staticmethod
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

    @experiment_route("/dashboard/export", methods=["GET"])
    @classmethod
    def export(cls):
        from .command_line import export__local

        with tempfile.TemporaryDirectory() as tempdir:
            ctx = Context(export__local)
            ctx.invoke(export__local, path=tempdir, n_parallel=None)

            file_basename = get_config().get("label")
            zip_filepath = shutil.make_archive(f"{file_basename}-data", "zip", tempdir)

            return send_file(zip_filepath, mimetype="zip")

    @experiment_route("/get_participant_info_for_debug_mode", methods=["GET"])
    @staticmethod
    def get_participant_info_for_debug_mode():
        config = get_config()
        if not config.get("mode") == "debug":
            return error_response()

        participant = Participant.query.first()
        json_data = {
            "id": participant.id,
            "assignment_id": participant.assignment_id,
            "page_uuid": participant.page_uuid,
        }
        logger.debug(
            f"Returning from /get_participant_info_for_debug_mode: {json_data}"
        )
        return json.dumps(json_data, default=serialise)

    @experiment_route("/fast-function-asset", methods=["GET"])
    @staticmethod
    def get_fast_function_asset():
        id = request.args.get("id")
        secret = request.args.get("secret")

        assert id
        assert secret

        id = int(id)

        asset = FastFunctionAsset.query.filter_by(id=id).one()
        suffix = asset.extension if asset.extension else ""

        with tempfile.NamedTemporaryFile(suffix=suffix) as temp_file:
            asset.export(temp_file.name)

            return send_file(temp_file.name, max_age=0)

    @experiment_route("/error-page", methods=["POST", "GET"])
    @classmethod
    def render_error(cls):
        request_data = request.form.get("request_data")
        participant_id = request.form.get("participant_id")
        compensate = True
        participant = None
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
                    participant.assignment_id, "Terminated calling /error-page route"
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
    def get_module_details_as_rendered_html(cls):
        exp = get_experiment()
        module = exp.timeline.get_module(request.values["moduleId"])
        return module.visualize()

    @experiment_route("/module/tooltip", methods=["POST"])
    @classmethod
    def get_module_tooltip_as_rendered_html(cls):
        exp = get_experiment()
        module = exp.timeline.get_module(request.values["moduleId"])
        return module.visualize_tooltip()

    @experiment_route("/module/progress_info", methods=["GET"])
    @classmethod
    def get_progress_info(cls):
        exp = get_experiment()
        config = get_config()
        progress_info = {
            "spending": {
                "amount_spent": exp.amount_spent(),
                "currency": config.currency,
                "soft_max_experiment_payment": exp.var.soft_max_experiment_payment,
                "hard_max_experiment_payment": exp.var.hard_max_experiment_payment,
            }
        }
        module_ids = request.args.getlist("module_ids[]")
        for module_id in module_ids:
            module = exp.timeline.modules[module_id]
            progress_info.update(module.get_progress_info())

        return jsonify(progress_info)

    @experiment_route("/module/update_spending_limits", methods=["POST"])
    @classmethod
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
        db.session.commit()
        return success_response()

    @experiment_route("/debugger/<password>", methods=["GET"])
    @classmethod
    def route_debugger(cls, password):
        exp = get_experiment()
        if password == "my-secure-password-195762":
            exp.new(db.session)
            rpdb.set_trace()
            return success_response()
        return error_response()

    @experiment_route("/node/<int:node_id>/fail", methods=["GET", "POST"])
    @staticmethod
    def fail_node(node_id):
        from dallinger.models import Node

        node = Node.query.filter_by(id=node_id).one()
        node.fail(reason="http_fail_route_called")
        db.session.commit()
        return success_response()

    @experiment_route("/info/<int:info_id>/fail", methods=["GET", "POST"])
    @staticmethod
    def fail_info(info_id):
        from dallinger.models import Info

        info = Info.query.filter_by(id=info_id).one()
        info.fail(reason="http_fail_route_called")
        db.session.commit()
        return success_response()

    @experiment_route("/network/<int:network_id>/grow", methods=["GET", "POST"])
    @classmethod
    def grow_network(cls, network_id):
        exp = get_experiment()
        from .trial.main import TrialNetwork

        network = TrialNetwork.query.filter_by(id=network_id).one()
        trial_maker = exp.timeline.get_trial_maker(network.trial_maker_id)
        trial_maker._grow_network(network, experiment=exp)
        db.session.commit()
        return success_response()

    @experiment_route(
        "/network/<int:network_id>/call_async_post_grow_network",
        methods=["GET", "POST"],
    )
    @staticmethod
    def call_async_post_grow_network(network_id):
        from .trial.main import TrialNetwork

        network = TrialNetwork.query.filter_by(id=network_id).one()
        trial_maker = get_trial_maker(network.trial_maker_id)

        WorkerAsyncProcess(
            network.async_post_grow_network,
            label="post_grow_network",
            timeout=trial_maker.async_timeout_sec,
            network=network,
        )
        db.session.commit()
        return success_response()

    # Lucid recruitment specific route
    @experiment_route("/terminate_participant", methods=["GET"])
    @classmethod
    def terminate_participant(cls):
        participant_id = request.values.get("participant_id")
        reason = request.values["reason"]
        external_submit_url = None

        try:
            participant = get_participant(participant_id)
            assignment_id = participant.assignment_id
            recruiter = get_experiment().recruiter
            external_submit_url = None
            if hasattr(recruiter, "external_submit_url"):
                external_submit_url = recruiter.external_submit_url(
                    assignment_id=assignment_id
                )
            if hasattr(recruiter, "terminate_participant"):
                recruiter.terminate_participant(assignment_id, reason)
                logger.info(
                    f"Terminating participant with RID {assignment_id} with reason '{reason}'"
                )

        except Exception as e:
            logger.error(
                f"Error terminating participant with RID '{assignment_id}': {e}"
            )

        return render_template_with_translations(
            "exit_recruiter_lucid.html",
            external_submit_url=external_submit_url,
        )

    @staticmethod
    def get_client_ip_address():
        if request.environ.get("HTTP_X_FORWARDED_FOR") is None:
            return request.environ["REMOTE_ADDR"]
        else:
            return request.environ["HTTP_X_FORWARDED_FOR"]

    @experiment_route("/set_locale_participant/<int:participant_id>", methods=["GET"])
    @classmethod
    def route_set_locale_participant(cls, participant_id):
        participant = cls.get_participant_from_participant_id(participant_id)
        try:
            old_locale = participant.var.locale
        except KeyError:
            old_locale = get_language()
        GET = request.args.to_dict()
        assert "locale" in GET, "locale not in GET"
        new_locale = GET["locale"]
        assert len(new_locale) == 2, "Locale must be a two-letter code"
        new_locale = new_locale.lower()
        participant.var.set("locale", new_locale)
        db.session.commit()
        logger.info(
            f"Updated locale from {old_locale} to {new_locale} for participant {participant.id}'."
        )
        return success_response()

    @experiment_route("/set_participant_as_aborted/<assignment_id>", methods=["GET"])
    @classmethod
    def route_set_participant_as_aborted(cls, assignment_id):  # TODO - update
        participant = cls.get_participant_from_assignment_id(assignment_id)
        participant.aborted = True
        if participant.module_state:
            participant.module_state.abort()
        db.session.commit()
        logger.info(f"Aborted participant with ID '{participant.id}'.")
        return success_response()

    @experiment_route("/abort/<assignment_id>", methods=["GET"])
    @classmethod
    def route_abort(cls, assignment_id):
        try:
            template_name = "abort_not_possible.html"
            participant = None
            participant_abort_info = None
            if assignment_id is not None:
                participant = cls.get_participant_from_assignment_id(assignment_id)
                if participant.calculate_bonus() >= get_and_load_config().get(
                    "min_accumulated_bonus_for_abort"
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
    def route_timeline(cls):
        unique_id = request.args.get("unique_id")
        mode = request.args.get("mode")
        participant = cls.get_participant_from_unique_id(unique_id)
        experiment = get_experiment()

        return cls._route_timeline(experiment, participant, mode)

    @classmethod
    def _route_timeline(cls, experiment, participant, mode):
        try:
            page = cls.get_current_page(experiment, participant)
            participant.client_ip_address = cls.get_client_ip_address()
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
                node=participant.current_trial.node
                if participant.current_trial
                else None,
                network=participant.current_trial.network
                if participant.current_trial
                else None,
            )
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
            "err-%s:%s",
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
        db.session.commit()

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

    @experiment_route("/timeline/progress_and_bonus", methods=["GET"])
    @classmethod
    def get_progress_and_bonus(cls):
        participant = get_participant(request.args.get("participantId"))
        progress_percentage = round(participant.progress * 100)
        min_pct = 5
        max_pct = 99
        if progress_percentage > max_pct:
            progress_percentage = max_pct
        elif progress_percentage < min_pct:
            progress_percentage = min_pct
        data = {
            "progressPercentage": progress_percentage,
            "progressPercentageStr": f"{progress_percentage}%",
        }
        if get_and_load_config().get("show_bonus"):
            performance_bonus = participant.performance_bonus
            basic_bonus = participant.time_credit.get_bonus()
            total_bonus = participant.calculate_bonus()
            data["bonus"] = {
                "basic": basic_bonus,
                "extra": performance_bonus,
                "total": total_bonus,
            }
        return data

    @experiment_route("/response", methods=["POST"])
    @classmethod
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

        db.session.commit()
        return res

    @experiment_route("/log/<level>/<unique_id>", methods=["POST"])
    @classmethod
    def http_log(cls, level, unique_id):
        participant = cls.get_participant_from_unique_id(unique_id)
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
    def participant_opened_devtools(cls, unique_id):
        participant = cls.get_participant_from_unique_id(unique_id)

        cls.check_unique_id(participant, unique_id)

        participant.var.opened_devtools = True
        db.session.commit()

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


def in_deployment_package():
    return bool(os.getenv("DEPLOYMENT_PACKAGE") or os.path.exists("DEPLOYMENT_PACKAGE"))


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
