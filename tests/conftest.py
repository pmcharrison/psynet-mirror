import sys
import time
import warnings

import pexpect
import pytest
import sqlalchemy.exc
from dallinger import db
from dallinger.config import get_config
from dallinger.models import Network, Node
from dallinger.pytest_dallinger import flush_output

import psynet.experiment
import psynet.utils
from psynet.command_line import (
    kill_chromedriver_processes,
    kill_psynet_chrome_processes,
    working_directory,
)
from psynet.data import init_db
from psynet.experiment import Experiment
from psynet.participant import Participant
from psynet.trial.main import TrialSource
from psynet.utils import clear_all_caches, disable_logger

warnings.filterwarnings("ignore", category=sqlalchemy.exc.SAWarning)


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


@pytest.fixture
def launched_experiment(request, env, clear_workers, experiment_directory):
    """
    This overrides the debug_experiment fixture in Dallinger to
    use PsyNet debug instead. Note that we use legacy mode for now.
    """
    print(f"Launching experiment in directory {experiment_directory}...")
    with working_directory(experiment_directory):
        init_db(drop_all=True)
        time.sleep(0.5)
        kill_psynet_chrome_processes()
        kill_chromedriver_processes()

        timeout = request.config.getvalue("recruiter_timeout", 120)

        # Seems to be important to load config before initializing the experiment,
        # something to do with duplicated SQLAlchemy imports
        config = get_config()
        if not config.ready:
            config.load()

        psynet.experiment.import_local_experiment()

        # Make sure debug server runs to completion with bots
        p = pexpect.spawn(
            "psynet",
            ["debug", "--no-browsers", "--verbose", "--legacy"],
            env=env,
            encoding="utf-8",
        )
        p.logfile = sys.stdout

        try:
            p.expect_exact("Server is running", timeout=timeout)
            yield p
        finally:
            try:
                flush_output(p, timeout=0.1)
                p.sendcontrol("c")
                flush_output(p, timeout=3)
                # Why do we need to call flush_output twice? Good question.
                # Something about calling p.sendcontrol("c") seems to disrupt the log.
                # Better to call it both before and after.
                kill_psynet_chrome_processes()
                kill_chromedriver_processes()
                clear_all_caches()
            except IOError:
                pass


@pytest.fixture(scope="class")
def demo_static(root):
    demo_setup("static")
    yield
    demo_teardown(root)


@pytest.fixture(scope="class")
def demo_custom_table_complex(root):
    demo_setup("custom_table_complex")
    yield
    demo_teardown(root)


@pytest.fixture(scope="class")
def demo_dense_color(root):
    demo_setup("dense_color")
    yield
    demo_teardown(root)


@pytest.fixture(scope="class")
def demo_gibbs(root):
    demo_setup("gibbs")
    yield
    demo_teardown(root)


@pytest.fixture(scope="class")
def demo_gmsi(root):
    demo_setup("demography/gmsi")
    yield
    demo_teardown(root)


@pytest.fixture(scope="class")
def demo_gmsi_short(root):
    demo_setup("demography/gmsi_short")
    yield
    demo_teardown(root)


@pytest.fixture(scope="class")
def demo_gmsi_two_modules_with_subscales(root):
    demo_setup("demography/gmsi_two_modules_with_subscales")
    yield
    demo_teardown(root)


@pytest.fixture(scope="class")
def demo_color_blindness(root):
    demo_setup("color_blindness")
    yield
    demo_teardown(root)


@pytest.fixture(scope="class")
def demo_color_vocabulary(root):
    demo_setup("color_vocabulary")
    yield
    demo_teardown(root)


@pytest.fixture(scope="class")
def demo_headphone_test(root):
    demo_setup("headphone_test")
    yield
    demo_teardown(root)


@pytest.fixture(scope="class")
def demo_language_tests(root):
    demo_setup("language_tests")
    yield
    demo_teardown(root)


@pytest.fixture(scope="class")
def demo_bot(root):
    demo_setup("bot")
    yield
    demo_teardown(root)


@pytest.fixture(scope="class")
def demo_mcmcp(root):
    demo_setup("mcmcp")
    yield
    demo_teardown(root)


@pytest.fixture(scope="class")
def demo_multi_page_maker(root):
    demo_setup("page_maker")
    yield
    demo_teardown(root)


@pytest.fixture(scope="class")
def demo_pickle_page(root):
    demo_setup("pickle_page")
    yield
    demo_teardown(root)


@pytest.fixture(scope="class")
def demo_static_audio(root):
    demo_setup("static_audio")
    yield
    demo_teardown(root)


@pytest.fixture(scope="class")
def demo_timeline(root):
    demo_setup("timeline")
    yield
    demo_teardown(root)


@pytest.fixture(scope="class")
def demo_timeline_with_error(root):
    demo_setup("timeline_with_error")
    yield
    demo_teardown(root)


@pytest.fixture(scope="class")
def demo_wait(root):
    demo_setup("wait")
    yield
    demo_teardown(root)


@pytest.fixture(scope="class")
def demo_unity_autoplay(root):
    demo_setup("unity_autoplay")
    yield
    demo_teardown(root)


@pytest.fixture
def experiment_module(db_session):
    return psynet.experiment.import_local_experiment().get("module")


@pytest.fixture
def experiment_class(experiment_module):
    import dallinger.experiment

    return dallinger.experiment.load()


@pytest.fixture
def experiment_object(experiment_class, db_session):
    return experiment_class(session=db_session)


@pytest.fixture
def prepopulated_database():
    from psynet.command_line import run_prepare_in_subprocess
    from psynet.experiment import ExperimentConfig

    database_is_populated = ExperimentConfig.query.count() > 0
    if not database_is_populated:
        db.session.commit()
        run_prepare_in_subprocess()


@pytest.fixture
def participant(db_session, experiment_object):

    from dallinger.config import get_config

    config = get_config()
    if not config.ready:
        config.load()
    p = Participant(
        experiment=experiment_object,
        recruiter_id="x",
        worker_id="x",
        assignment_id="x",
        hit_id="x",
        mode="debug",
    )
    db_session.add(p)
    db_session.commit()
    return p


@pytest.fixture
def node(db_session, network, prepopulated_database):
    nodes = Node.query.all()
    return [
        n for n in nodes if not isinstance(n, TrialSource) and n.definition is not None
    ][0]


@pytest.fixture
def network(db_session, experiment_module, prepopulated_database):
    import time

    time.sleep(0.1)  # wait for networks to be created
    return Network.query.all()[0]


@pytest.fixture
def trial_class(experiment_module):
    return experiment_module.AnimalTrial


@pytest.fixture
def trial_maker(experiment_module):
    return experiment_module.trial_maker


@pytest.fixture
def trial(
    trial_class, db_session, experiment_object, node, participant, prepopulated_database
):
    t = trial_class(
        experiment=experiment_object,
        node=node,
        participant=participant,
        propagate_failure=False,
        is_repeat_trial=False,
    )
    db_session.add(t)
    db_session.commit()
    return t


@pytest.fixture
def deployment_id():
    from psynet.experiment import Experiment

    id_ = "Test deployment"
    old_id = Experiment.deployment_id
    Experiment.deployment_id = id_
    yield id_
    Experiment.deployment_id = old_id
