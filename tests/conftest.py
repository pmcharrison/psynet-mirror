import pytest
import os
from psynet.trial.non_adaptive import StimulusVersion
# from psynet.experiment import Experiment
# from psynet.demos.non_adaptive.experiment import Exp as Experiment
from psynet.participant import Participant
# from psynet.demos.non_adaptive.experiment import AnimalTrial as Trial
from dallinger.models import Node, Network
from psynet.trial.main import Trial

@pytest.fixture(scope="class")
def demo_non_adaptive_dir(root):
    os.chdir(os.path.join(os.path.dirname(__file__), "..", "psynet/demos/non_adaptive"))
    import psynet.utils
    psynet.utils.import_local_experiment()
    yield
    os.chdir(root)

# @pytest.mark.usefixtures("demo_non_adaptive_dir")

@pytest.fixture
def experiment_module(db_session):
    import psynet.utils
    return psynet.utils.import_local_experiment()

@pytest.fixture
def experiment_class(experiment_module): #, demo_non_adaptive_dir):
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
    return StimulusVersion.query.all()[0]

@pytest.fixture
def network(db_session, experiment_module):
    import time
    time.sleep(0.5) # wait for networks to be created
    return Network.query.all()[0]

@pytest.fixture
def trial_class(experiment_module):
    return experiment_module.AnimalTrial

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
