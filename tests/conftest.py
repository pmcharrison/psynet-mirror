import os
import warnings

import pytest
import sqlalchemy.exc
from dallinger import db
from dallinger.models import Network, Node
from dallinger.nodes import Source

import psynet.utils
from psynet.command_line import (
    kill_chromedriver_processes,
    kill_psynet_chrome_processes,
)
from psynet.participant import Participant

ACTIVE_EXPERIMENT = None

warnings.filterwarnings("ignore", category=sqlalchemy.exc.SAWarning)


def demo_setup(demo):
    global ACTIVE_EXPERIMENT
    ACTIVE_EXPERIMENT = demo
    os.chdir(os.path.join(os.path.dirname(__file__), "..", f"demos/{demo}"))
    db.init_db(drop_all=True)
    kill_psynet_chrome_processes()
    kill_chromedriver_processes()
    psynet.utils.import_local_experiment()


def demo_teardown(root):
    global ACTIVE_EXPERIMENT
    ACTIVE_EXPERIMENT = None
    os.chdir(root)
    kill_psynet_chrome_processes()
    kill_chromedriver_processes()


@pytest.fixture(scope="class")
def demo_static(root):
    demo_setup("static")
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
def demo_mcmcp(root):
    demo_setup("mcmcp")
    yield
    demo_teardown(root)


@pytest.fixture(scope="class")
def demo_multi_page_maker(root):
    demo_setup("multi_page_maker")
    yield
    demo_teardown(root)


@pytest.fixture
def experiment_module(db_session):
    import psynet.utils

    return psynet.utils.import_local_experiment().get("module")


@pytest.fixture
def experiment_class(experiment_module):
    import dallinger.experiment

    return dallinger.experiment.load()


@pytest.fixture
def experiment_object(experiment_class, db_session):
    return experiment_class(session=db_session)


@pytest.fixture
def participant(db_session, experiment_object):
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
def node(db_session, network):
    # if ACTIVE_EXPERIMENT == "singing_iterated":
    #     nodes = Node.query.all()
    #     return [
    #         n for n in nodes if not isinstance(n, Source) and n.definition is not None
    #     ][0]
    if ACTIVE_EXPERIMENT == "mcmcp":
        nodes = Node.query.all()
        return [
            n for n in nodes if not isinstance(n, Source) and n.definition is not None
        ][0]
    else:
        raise RuntimeError("Unrecognized ACTIVE_EXPERIMENT: " + ACTIVE_EXPERIMENT)


@pytest.fixture
def network(db_session, experiment_module):
    import time

    time.sleep(0.5)  # wait for networks to be created
    return Network.query.all()[0]


@pytest.fixture
def trial_class(experiment_module):
    if ACTIVE_EXPERIMENT == "static":
        return experiment_module.AnimalTrial
    else:
        raise NotImplementedError
    # elif ACTIVE_EXPERIMENT == "singing_iterated":
    #     return experiment_module.CustomTrial


@pytest.fixture
def trial_maker(experiment_module):
    if ACTIVE_EXPERIMENT == "static":
        return experiment_module.trial_maker
    else:
        raise NotImplementedError


@pytest.fixture
def trial(trial_class, db_session, experiment_object, node, participant):
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
