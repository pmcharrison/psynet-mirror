import logging
import os
import re
import subprocess
import sys
import time
import warnings
from pathlib import Path

import dallinger.pytest_dallinger
import pexpect
import pexpect.exceptions
import pytest
import sqlalchemy.exc
from cached_property import cached_property
from dallinger import db, pytest_dallinger
from dallinger.bots import BotBase
from dallinger.config import get_config
from dallinger.models import Node
from dallinger.pytest_dallinger import flush_output
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .command_line import (
    clean_sys_modules,
    kill_chromedriver_processes,
    kill_psynet_chrome_processes,
    working_directory,
)
from .data import init_db
from .experiment import Experiment, get_experiment, import_local_experiment
from .redis import redis_vars
from .trial.main import TrialNetwork
from .utils import clear_all_caches, disable_logger, wait_until

logger = logging.getLogger(__file__)
warnings.filterwarnings("ignore", category=sqlalchemy.exc.SAWarning)


def assert_text(driver, element_id, value):
    def get_element():
        try:
            return driver.find_element(By.ID, element_id)
        except NoSuchElementException:
            pass

    wait_until(
        get_element,
        max_wait=5,
        error_message=f"Could not find element with ID {element_id}",
    )
    element = get_element()

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


def page_loaded(driver):
    return driver.execute_script("return document.readyState == 'complete'")


def psynet_loaded(driver):
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


def next_page(driver, button_id, finished=False, poll_interval=0.25, max_wait=5.0):
    def get_uuid():
        return driver.execute_script("return pageUuid")

    def click_button():
        button = driver.find_element(By.ID, button_id)
        button.click()

    wait_until(
        psynet_loaded,
        max_wait=max_wait,
        error_message="Page never became ready.",
        driver=driver,
    )

    old_uuid = get_uuid()
    click_button()
    if not finished:
        if driver.current_url == "http://localhost:5000/error-page":
            raise RuntimeError(
                "Unexpectedly hit an error page, check the server logs for details."
            )

        wait_until(
            lambda: psynet_loaded(driver) and get_uuid() != old_uuid,
            max_wait=max_wait,
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


@pytest.fixture(scope="class")
def experiment_directory(request):
    return request.param


@pytest.fixture(scope="class")
def in_experiment_directory(experiment_directory):
    redis_vars.clear()
    with working_directory(experiment_directory):
        yield experiment_directory
    clean_sys_modules()
    clear_all_caches()


@pytest.fixture(scope="class")
def skip_constraints_check():
    original = os.getenv("SKIP_DEPENDENCY_CHECK", None)
    os.environ["SKIP_DEPENDENCY_CHECK"] = "1"
    yield
    if original is None:
        del os.environ["SKIP_DEPENDENCY_CHECK"]
    else:
        os.environ["SKIP_DEPENDENCY_CHECK"] = original


# dallinger_clear_workers = pytest_dallinger.clear_workers.__wrapped__


@pytest.fixture(scope="class")
def clear_workers():
    def _zap():
        kills = [["pkill", "-f", "heroku"]]
        for kill in kills:
            try:
                subprocess.check_call(kill)
            except Exception as e:
                if e.returncode != 1:
                    raise

    _zap()
    yield
    _zap()


pytest_dallinger.clear_workers = clear_workers


def patch_pexpect_error_reporter(p):
    p.str_last_chars = 2000
    # original_reporter = pexpect.spawn.__str__
    #
    # def __str__(self):
    #     original = original_reporter(self)
    #     new = "\n".join(
    #         [
    #             "~~~",
    #             "Full error context:",
    #             "",
    #             self.before[-10000:],
    #             "~~~",
    #         ]
    #     )
    #     return original + "\n\n" + new
    #
    # pexpect.spawn.__str__ = __str__


@pytest.fixture(scope="class")
def debug_experiment(
    request,
    env,
    clear_workers,
    in_experiment_directory,
    db_session,
    skip_constraints_check,
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
    timeout = 60

    get_experiment()

    config = get_config()
    if not config.ready:
        config.load()

    p = pexpect.spawn(
        "psynet",
        ["debug", "local", "--legacy", "--no-browsers"],
        env=env,
        encoding="utf-8",
    )
    patch_pexpect_error_reporter(p)
    # p.str_last_chars = 2000
    p.logfile = sys.stdout
    p.timeout = timeout

    try:
        # assert_logs_contain(
        #     "Experiment launch complete!",
        #     process=p,
        #     timeout=timeout,
        # )
        p.expect_exact("Experiment launch complete!", timeout=timeout)
        yield p
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


dallinger.pytest_dallinger.debug_experiment = debug_experiment


@pytest.fixture(scope="class")
def launched_experiment(debug_experiment):
    return get_experiment()


@pytest.fixture(scope="class")
def debug_server_process(debug_experiment):
    return debug_experiment


@pytest.fixture(scope="class")
def db_session(in_experiment_directory):
    import dallinger.db

    # The drop_all call can hang without this; see:
    # https://stackoverflow.com/questions/13882407/sqlalchemy-blocked-on-dropping-tables
    dallinger.db.session.close()
    session = dallinger.db.init_db(drop_all=True)
    yield session
    session.rollback()
    session.close()


dallinger.pytest_dallinger.db_session = db_session


@pytest.fixture(scope="class")
def imported_experiment(launched_experiment):
    return import_local_experiment()


@pytest.fixture(scope="class")
def experiment_module(imported_experiment):
    return imported_experiment["module"]


@pytest.fixture(scope="class")
def experiment_class(imported_experiment):
    return imported_experiment["class"]


@pytest.fixture(scope="class")
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


@pytest.fixture(scope="class")
def participant(launched_experiment):
    from psynet.bot import Bot

    return Bot()


@pytest.fixture(scope="class")
def node(launched_experiment):
    nodes = Node.query.all()
    return [n for n in nodes if n.definition is not None][0]


@pytest.fixture(scope="class")
def network(launched_experiment):
    return TrialNetwork.query.all()[0]


@pytest.fixture(scope="class")
def trial_class(experiment_module):
    return experiment_module.AnimalTrial


@pytest.fixture
def trial_maker(experiment_module):
    return experiment_module.trial_maker


@pytest.fixture(scope="class")
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


# def assert_logs_contain(text, process, regex=False, timeout=5):
#     try:
#         if regex:
#             process.expect(text, timeout=timeout)
#         else:
#             process.expect_exact(text, timeout=timeout)
#     except (pexpect.EOF, pexpect.TIMEOUT):
#         print("Failed to find match in server logs.")
#         # print("History:")
#         # wrapper = textwrap.TextWrapper(initial_indent=4, subsequent_indent=4)
#         # print(wrapper.fill(str(process.before)))
#         raise


def path_to_demo(demo):
    return Path(__file__).parent.parent.joinpath("demos").joinpath(demo).__str__()
