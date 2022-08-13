import logging
import os
import re
import sys
import time
import warnings

import pexpect
import pytest
import sqlalchemy.exc
from cached_property import cached_property
from dallinger import db
from dallinger.bots import BotBase
from dallinger.config import get_config
from dallinger.models import Network, Node
from dallinger.pytest_dallinger import flush_output
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import psynet.experiment
import psynet.utils
from psynet.command_line import (
    clean_sys_modules,
    kill_chromedriver_processes,
    kill_psynet_chrome_processes,
    working_directory,
)
from psynet.data import init_db
from psynet.experiment import Experiment
from psynet.trial.main import TrialSource
from psynet.utils import clear_all_caches, disable_logger

from .utils import wait_until

logger = logging.getLogger(__file__)
warnings.filterwarnings("ignore", category=sqlalchemy.exc.SAWarning)


def assert_text(driver, element_id, value):
    element = driver.find_element(By.ID, element_id)

    def sanitize(x):
        pattern = re.compile(r"\s+")
        return re.sub(pattern, " ", x).strip()

    if sanitize(element.text) != sanitize(value):
        raise AssertionError(
            f"""
            Found some unexpected HTML text.

            Expected: {sanitize(value)}

            Found: {sanitize(element.text)}
            """
        )


def bot_class(headless=None):
    if headless is None:
        headless_env = os.getenv("HEADLESS", default="FALSE").upper()
        assert headless_env in ["TRUE", "FALSE"]
        headless = headless_env == "TRUE"

    class PYTEST_BOT_CLASS(BotBase):
        def sign_up(self):
            """Accept HIT, give consent and start experiment.

            This uses Selenium to click through buttons on the ad,
            consent, and instruction pages.
            """
            try:
                self.driver.get(self.URL)
                logger.info("Loaded ad page.")
                begin = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn-primary"))
                )
                begin.click()
                logger.info("Clicked begin experiment button.")
                WebDriverWait(self.driver, 10).until(
                    lambda d: len(d.window_handles) == 2
                )
                self.driver.switch_to.window(self.driver.window_handles[-1])
                self.driver.set_window_size(1024, 768)
                logger.info("Switched to experiment popup.")
                consent = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "consent"))
                )
                consent.click()
                logger.info("Clicked consent button.")
                return True
            except TimeoutException:
                logger.error("Error during experiment sign up.")
                return False

        def sign_off(self):
            try:
                logger.info("Clicked submit questionnaire button.")
                self.driver.switch_to.window(self.driver.window_handles[0])
                self.driver.set_window_size(1024, 768)
                logger.info("Switched back to initial window.")
                return True
            except TimeoutException:
                logger.error("Error during experiment sign off.")
                return False

        @cached_property
        def driver(self):
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options

            chrome_options = Options()
            chrome_options.add_argument("--remote-debugging-port=9222")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--no-sandbox")

            if headless:
                chrome_options.add_argument("--headless")

            return webdriver.Chrome(options=chrome_options)

    return PYTEST_BOT_CLASS


def next_page(driver, button_id, finished=False, poll_interval=0.25, max_wait=5.0):
    def get_uuid():
        return driver.execute_script("return pageUuid")

    def click_button():
        button = driver.find_element(By.ID, button_id)
        button.click()

    def is_page_ready():
        psynet_loaded = driver.execute_script(
            "try { return psynet != undefined } catch(e) { if (e instanceof ReferenceError) { return false }}"
        )
        if psynet_loaded:
            page_loaded = driver.execute_script("return psynet.pageLoaded")
            if page_loaded:
                response_enabled = driver.execute_script(
                    "return psynet.trial.events.responseEnable.happened"
                )
                if response_enabled:
                    return True
        return False

    wait_until(
        is_page_ready,
        max_wait=15.0,
        error_message="Page never became ready.",
    )

    old_uuid = get_uuid()
    click_button()
    if not finished:
        wait_until(
            lambda: is_page_ready() and get_uuid() != old_uuid,
            max_wait=1000.0,  # todo - revert to `max_wait`
            error_message="Failed to load new page.",
        )


@pytest.fixture()
def config():
    try:
        Experiment.extra_parameters()
    except KeyError as err:
        if "is already registered" in str(err):
            pass
        else:
            raise

    c = get_config()
    with disable_logger():
        # We disable the logger because Dallinger prints an error message to the log
        # when importing the config file outside a real experiment
        if not c.ready:
            c.load()

    return c


@pytest.fixture
def deployment_info():
    from psynet import deployment_info

    deployment_info.reset()
    deployment_info.write(deployment_id="Test deployment")
    yield
    deployment_info.delete()


@pytest.fixture()
def experiment_directory(request):
    return request.param


@pytest.fixture()
def in_experiment_directory(experiment_directory):
    with working_directory(experiment_directory):
        yield experiment_directory
    clean_sys_modules()
    clear_all_caches()


@pytest.fixture
def launched_experiment(
    request, env, clear_workers, in_experiment_directory, db_session
):
    """
    This overrides the debug_experiment fixture in Dallinger to
    use PsyNet debug instead. Note that we use legacy mode for now.
    """
    print(f"Launching experiment in directory '{in_experiment_directory}'...")
    init_db(drop_all=True)
    time.sleep(0.5)
    kill_psynet_chrome_processes()
    kill_chromedriver_processes()

    # timeout = request.config.getvalue("recruiter_timeout", 120)
    timeout = 45

    # Seems to be important to load config before initializing the experiment,
    # something to do with duplicated SQLAlchemy imports
    config = get_config()
    if not config.ready:
        config.load()

    exp = psynet.experiment.get_experiment()

    # Make sure debug server runs to completion with bots
    p = pexpect.spawn(
        "psynet",
        ["debug", "--no-browsers", "--verbose", "--legacy"],
        env=env,
        encoding="utf-8",
    )
    p.logfile = sys.stdout

    try:
        p.expect_exact("Experiment launch complete!", timeout=timeout)

        yield exp
    finally:
        try:
            flush_output(p, timeout=0.1)
            p.sendcontrol("c")
            flush_output(p, timeout=3)
            # Why do we need to call flush_output twice? Good question.
            # Something about calling p.sendcontrol("c") seems to disrupt the log.
            # Better to call it both before and after.
        except (IOError, pexpect.exceptions.EOF):
            pass
        kill_psynet_chrome_processes()
        kill_chromedriver_processes()
        clear_all_caches()


@pytest.fixture
def db_session(in_experiment_directory):
    import dallinger.db

    # The drop_all call can hang without this; see:
    # https://stackoverflow.com/questions/13882407/sqlalchemy-blocked-on-dropping-tables
    dallinger.db.session.close()
    session = dallinger.db.init_db(drop_all=True)
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def imported_experiment(launched_experiment):
    return psynet.experiment.import_local_experiment()


@pytest.fixture
def experiment_module(imported_experiment):
    return imported_experiment["module"]


@pytest.fixture
def experiment_class(imported_experiment):
    return imported_experiment["class"]


@pytest.fixture
def experiment_object(experiment_class):
    return experiment_class()


# @pytest.fixture
# def prepopulated_database(in_experiment_directory):
#     from psynet.command_line import run_prepare_in_subprocess
#     from psynet.experiment import ExperimentConfig
#
#     database_is_populated = ExperimentConfig.query.count() > 0
#     if not database_is_populated:
#         db.session.commit()
#         run_prepare_in_subprocess()


@pytest.fixture
def participant(launched_experiment):
    from psynet.bot import Bot

    return Bot()


@pytest.fixture
def node(launched_experiment):
    nodes = Node.query.all()
    return [
        n for n in nodes if not isinstance(n, TrialSource) and n.definition is not None
    ][0]


@pytest.fixture
def network(launched_experiment):
    return Network.query.all()[0]


@pytest.fixture
def trial_class(experiment_module):
    return experiment_module.AnimalTrial


@pytest.fixture
def trial_maker(experiment_module):
    return experiment_module.trial_maker


@pytest.fixture
def trial(launched_experiment, trial_class, node, participant):
    t = trial_class(
        experiment=launched_experiment,
        node=node,
        participant=participant,
        propagate_failure=False,
        is_repeat_trial=False,
    )
    db.session.add(t)
    db.session.commit()
    return t


@pytest.fixture
def deployment_id():
    from psynet.experiment import Experiment

    id_ = "Test deployment"
    old_id = Experiment.deployment_id
    Experiment.deployment_id = id_
    yield id_
    Experiment.deployment_id = old_id
