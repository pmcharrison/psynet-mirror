import uuid

import pytest
from dallinger import db

from psynet.experiment import get_experiment
from psynet.participant import Participant
from psynet.pytest_psynet import path_to_test_experiment
from psynet.trial.chain import ChainNetwork, ChainNode, ChainTrial, ChainTrialMaker
from psynet.trial.graph import (
    GraphChainEdge,
    GraphChainNetwork,
    GraphChainNode,
    GraphChainTrial,
    GraphChainTrialMaker,
    GraphChainVertex,
)
from psynet.trial.static import StaticNetwork


class GrowthQueryTrial(ChainTrial):
    time_estimate = 1

    def make_definition(self, experiment, participant):
        return self.node.definition


class GrowthQueryNode(ChainNode):
    def create_initial_seed(self, experiment, participant):
        return {"x": 0}

    def summarize_trials(self, trials, experiment, participant):
        return {"x": trials[0].answer}

    def create_definition_from_seed(self, seed, experiment, participant):
        return seed


class GrowthQueryGraphTrial(GraphChainTrial):
    time_estimate = 1


class GrowthQueryGraphNode(GraphChainNode):
    @staticmethod
    def generate_class_seed(vertex=None):
        return [{"vertex_id": vertex, "content": vertex, "is_center": True}]


class GrowthQueryGraphTrialMaker(GraphChainTrialMaker):
    pass


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


def chain_trial_maker(**kwargs):
    args = dict(
        id_="growth_query",
        node_class=GrowthQueryNode,
        trial_class=GrowthQueryTrial,
        chain_type="across",
        expected_trials_per_participant=1,
        max_trials_per_participant=1,
        chains_per_experiment=1,
        max_nodes_per_chain=2,
        trials_per_node=1,
        recruit_mode="n_trials",
    )
    return ChainTrialMaker(**{**args, **kwargs})


def create_chain_network(trial_maker, experiment, *, network_class=ChainNetwork):
    start_node = trial_maker.node_class(definition={"x": 0})
    network = network_class(
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


def add_trial(
    trial_class, node, participant, *, answer=1, finalized=True, failed=False
):
    trial = trial_class(
        experiment=get_experiment(),
        node=node,
        participant=participant,
        propagate_failure=False,
        is_repeat_trial=False,
    )
    trial.answer = answer
    trial.complete = finalized
    trial.finalized = finalized
    trial.failed = failed
    db.session.add(trial)
    db.session.flush()
    return trial


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory")
def test_ready_to_grow_query_uses_live_trial_state(db_session, participant):
    exp = get_experiment()
    trial_maker = chain_trial_maker()
    ready_network = create_chain_network(trial_maker, exp)
    pending_network = create_chain_network(trial_maker, exp)

    add_trial(GrowthQueryTrial, ready_network.head, participant, finalized=True)
    add_trial(GrowthQueryTrial, pending_network.head, participant, finalized=False)
    db.session.commit()

    ready_ids = {n.id for n in trial_maker.get_networks_ready_to_grow()}

    assert ready_network.id in ready_ids
    assert pending_network.id not in ready_ids


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory")
def test_can_spawn_excludes_static_networks_from_growth(db_session, participant):
    exp = get_experiment()
    trial_maker = chain_trial_maker()
    network = create_chain_network(trial_maker, exp, network_class=StaticNetwork)
    add_trial(GrowthQueryTrial, network.head, participant, finalized=True)
    db.session.commit()

    assert network.head.can_spawn is False
    assert trial_maker.get_networks_ready_to_grow() == []


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory")
def test_grow_network_uses_live_readiness_not_cached_flag(db_session, participant):
    exp = get_experiment()
    trial_maker = chain_trial_maker()
    network = create_chain_network(trial_maker, exp)
    add_trial(GrowthQueryTrial, network.head, participant, answer={"x": 1})
    db.session.commit()

    assert trial_maker.grow_network(network, exp) is True
    assert network.head.degree == 1


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory")
def test_ready_to_spawn_access_has_migration_error(db_session):
    exp = get_experiment()
    trial_maker = chain_trial_maker()
    network = create_chain_network(trial_maker, exp)

    with pytest.raises(AttributeError, match="ready_to_spawn has been removed"):
        network.ready_to_spawn

    with pytest.raises(AttributeError, match="check_ready_to_spawn"):
        network.head.check_ready_to_spawn()


def graph_trial_maker():
    return make_graph_trial_maker(
        {
            "vertices": [1, 2, 3],
            "edges": [
                {"origin": 1, "target": 3},
                {"origin": 2, "target": 3},
            ],
        }
    )


def make_graph_trial_maker(network_structure):
    return GrowthQueryGraphTrialMaker(
        id_="graph_growth_query",
        node_class=GrowthQueryGraphNode,
        trial_class=GrowthQueryGraphTrial,
        network_structure=network_structure,
        chain_type="across",
        expected_trials_per_participant=1,
        max_trials_per_participant=1,
        chains_per_participant=None,
        trials_per_node=1,
        balance_across_chains=False,
        check_performance_at_end=False,
        check_performance_every_trial=False,
        recruit_mode="n_trials",
        target_n_participants=None,
        max_nodes_per_chain=2,
    )


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory")
def test_graph_topology_is_stored_in_normalized_tables(db_session):
    trial_maker = graph_trial_maker()
    trial_maker.create_networks_across(get_experiment())

    assert GraphChainVertex.query.filter_by(trial_maker_id=trial_maker.id).count() == 3
    assert GraphChainEdge.query.filter_by(trial_maker_id=trial_maker.id).count() == 2

    network = GraphChainNetwork.query.filter_by(
        trial_maker_id=trial_maker.id, vertex_id=3
    ).one()
    assert network.incoming_vertex_ids == [1, 2]
    assert network.outgoing_vertex_ids == []


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory")
def test_graph_readiness_waits_for_all_incoming_heads(db_session, participant):
    trial_maker = graph_trial_maker()
    trial_maker.create_networks_across(get_experiment())
    networks = {
        n.vertex_id: n
        for n in GraphChainNetwork.query.filter_by(trial_maker_id=trial_maker.id).all()
    }

    add_trial(GrowthQueryGraphTrial, networks[3].head, participant, finalized=True)
    db.session.commit()
    ready_ids = {n.id for n in trial_maker.get_networks_ready_to_grow()}
    assert networks[3].id not in ready_ids

    add_trial(GrowthQueryGraphTrial, networks[1].head, participant, finalized=True)
    db.session.commit()
    ready_ids = {n.id for n in trial_maker.get_networks_ready_to_grow()}
    assert networks[3].id not in ready_ids

    add_trial(GrowthQueryGraphTrial, networks[2].head, participant, finalized=True)
    db.session.commit()
    ready_ids = {n.id for n in trial_maker.get_networks_ready_to_grow()}
    assert networks[3].id in ready_ids


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory")
def test_graph_growth_processes_ready_cycle_as_one_wave(db_session, participant):
    trial_maker = make_graph_trial_maker(
        {
            "vertices": [1, 2, 3],
            "edges": [
                {"origin": 1, "target": 2},
                {"origin": 2, "target": 1},
                {"origin": 2, "target": 3},
                {"origin": 3, "target": 2},
            ],
        }
    )
    trial_maker.create_networks_across(get_experiment())
    networks = GraphChainNetwork.query.filter_by(trial_maker_id=trial_maker.id).all()

    for network in networks:
        add_trial(GrowthQueryGraphTrial, network.head, participant, finalized=True)
    db.session.commit()

    ready_networks = trial_maker.get_networks_ready_to_grow()
    assert {network.vertex_id for network in ready_networks} == {1, 2, 3}

    for network in ready_networks:
        trial_maker.call_grow_network(network, check_readiness=False)

    assert {network.head.degree for network in networks} == {1}
