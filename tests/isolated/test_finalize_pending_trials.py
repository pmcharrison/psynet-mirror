import uuid

import pytest
from dallinger import db

from psynet.experiment import get_experiment
from psynet.participant import Participant
from psynet.pytest_psynet import path_to_test_experiment
from psynet.trial.chain import ChainNetwork, ChainNode, ChainTrial, ChainTrialMaker
from psynet.trial.main import Trial


class FinalizeBackstopTrial(ChainTrial):
    time_estimate = 1

    def make_definition(self, experiment, participant):
        return self.node.definition

    def on_finalized(self):
        # Skip the chain growth fast-path; this test only covers finalization.
        Trial.on_finalized(self)


class FinalizeBackstopNode(ChainNode):
    def create_initial_seed(self, experiment, participant):
        return {"x": 0}

    def summarize_trials(self, trials, experiment, participant):
        return {"x": trials[0].answer}

    def create_definition_from_seed(self, seed, experiment, participant):
        return seed


@pytest.fixture
def participant(db_session):
    exp = get_experiment()
    participant = Participant(
        experiment=exp,
        recruiter_id="hotair",
        worker_id=str(uuid.uuid4()),
        hit_id=str(uuid.uuid4()),
        assignment_id=str(uuid.uuid4()),
        mode="debug",
    )
    db.session.add(participant)
    db.session.flush()
    return participant


def _chain_trial_maker():
    return ChainTrialMaker(
        id_="finalize_backstop",
        node_class=FinalizeBackstopNode,
        trial_class=FinalizeBackstopTrial,
        chain_type="across",
        expected_trials_per_participant=1,
        max_trials_per_participant=1,
        chains_per_experiment=1,
        max_nodes_per_chain=2,
        trials_per_node=1,
        recruit_mode="n_trials",
    )


def _create_network(trial_maker, experiment):
    start_node = trial_maker.node_class(definition={"x": 0})
    network = ChainNetwork(
        trial_maker_id=trial_maker.id,
        start_node=start_node,
        experiment=experiment,
        chain_type=trial_maker.chain_type,
        trials_per_node=trial_maker.trials_per_node,
        target_n_nodes=trial_maker.max_nodes_per_chain,
    )
    db.session.add(network)
    db.session.flush()
    return network


def _add_complete_unfinalized_trial(node, participant, **kwargs):
    trial = FinalizeBackstopTrial(
        experiment=get_experiment(),
        node=node,
        participant=participant,
        propagate_failure=False,
        is_repeat_trial=False,
    )
    trial.answer = 1
    trial.complete = True
    trial.finalized = False
    for key, value in kwargs.items():
        setattr(trial, key, value)
    db.session.add(trial)
    db.session.flush()
    return trial


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory")
def test_finalize_pending_trials_recovers_missed_callback(db_session, participant):
    exp = get_experiment()
    trial_maker = _chain_trial_maker()
    network = _create_network(trial_maker, exp)
    trial = _add_complete_unfinalized_trial(network.head, participant)
    db.session.commit()

    assert trial.finalized is False
    finalized_count = Trial.finalize_pending_trials()
    db.session.commit()

    assert finalized_count == 1
    assert trial.finalized is True


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory")
def test_finalize_pending_trials_skips_blocked_trials(db_session, participant):
    exp = get_experiment()
    trial_maker = _chain_trial_maker()
    network = _create_network(trial_maker, exp)
    trial = _add_complete_unfinalized_trial(
        network.head,
        participant,
        async_post_trial_requested=True,
        async_post_trial_complete=False,
    )
    db.session.commit()

    assert Trial.get_trials_ready_to_finalize() == []
    assert Trial.finalize_pending_trials() == 0
    assert trial.finalized is False
