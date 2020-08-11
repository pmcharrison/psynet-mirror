import pytest
import os
import warnings
import sqlalchemy.exc

from psynet.trial.non_adaptive import StimulusVersion
from psynet.participant import Participant
from dallinger.models import Node, Network
from dallinger.nodes import Source

ACTIVE_EXPERIMENT = None

warnings.filterwarnings("ignore", category=sqlalchemy.exc.SAWarning)

@pytest.fixture(scope="class")
def demo_non_adaptive(root):
    global ACTIVE_EXPERIMENT
    ACTIVE_EXPERIMENT = "non_adaptive"
    os.chdir(os.path.join(os.path.dirname(__file__), "..", "psynet/demos/non_adaptive"))
    import psynet.utils
    psynet.utils.import_local_experiment()
    yield
    os.chdir(root)
    ACTIVE_EXPERIMENT = None

@pytest.fixture(scope="class")
def demo_iterated_singing(root):
    global ACTIVE_EXPERIMENT
    ACTIVE_EXPERIMENT = "iterated_singing"
    os.chdir(os.path.join(os.path.dirname(__file__), "..", "psynet/demos/iterated_singing"))
    import psynet.utils
    psynet.utils.import_local_experiment()
    yield
    os.chdir(root)
    ACTIVE_EXPERIMENT = None

@pytest.fixture(scope="class")
def demo_mcmcp(root):
    global ACTIVE_EXPERIMENT
    ACTIVE_EXPERIMENT = "mcmcp"
    os.chdir(os.path.join(os.path.dirname(__file__), "..", "psynet/demos/mcmcp"))
    import psynet.utils
    psynet.utils.import_local_experiment()
    yield
    os.chdir(root)
    ACTIVE_EXPERIMENT = None

# @pytest.mark.usefixtures("demo_non_adaptive_dir")

@pytest.fixture
def experiment_module(db_session):
    import psynet.utils
    return psynet.utils.import_local_experiment()

@pytest.fixture
def experiment_class(experiment_module):
    import dallinger.experiment
    return dallinger.experiment.load()

@pytest.fixture
def experiment_object(experiment_class, db_session):
    return experiment_class(session=db_session)

@pytest.fixture
def participant(db_session):
    p = Participant(
        recruiter_id="x",
        worker_id="x",
        assignment_id="x",
        hit_id="x",
        mode="debug")
    db_session.add(p)
    db_session.commit()
    return p

@pytest.fixture
def node(db_session, network):
    if ACTIVE_EXPERIMENT == "non_adaptive":
        return StimulusVersion.query.all()[0]
    elif ACTIVE_EXPERIMENT == "iterated_singing":
        nodes = Node.query.all()
        return [n for n in nodes if not isinstance(n, Source) and n.definition is not None][0]
    elif ACTIVE_EXPERIMENT == "mcmcp":
        nodes = Node.query.all()
        return [n for n in nodes if not isinstance(n, Source) and n.definition is not None][0]
    else:
        raise RuntimeError("Unrecognised ACTIVE_EXPERIMENT: " + ACTIVE_EXPERIMENT)

@pytest.fixture
def network(db_session, experiment_module):
    import time
    time.sleep(0.5) # wait for networks to be created
    return Network.query.all()[0]

@pytest.fixture
def trial_class(experiment_module):
    if ACTIVE_EXPERIMENT == "non_adaptive":
        return experiment_module.AnimalTrial
    elif ACTIVE_EXPERIMENT == "iterated_singing":
        return experiment_module.CustomTrial

@pytest.fixture
def trial_maker(experiment_module):
    if ACTIVE_EXPERIMENT == "non_adaptive":
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
        is_repeat_trial=False
    )
    db_session.add(t)
    db_session.commit()
    return t
