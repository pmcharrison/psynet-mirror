import uuid

import pytest
from dallinger import db
from sqlalchemy import inspect

from psynet.experiment import get_experiment
from psynet.participant import Participant
from psynet.pytest_psynet import path_to_test_experiment
from psynet.sqlalchemy_profiling import (
    assert_no_n_plus_one,
    assert_query_count,
    sqlalchemy_profile,
)
from psynet.trial.chain import (
    ChainNetwork,
    ChainNode,
    ChainTrial,
    ChainTrialMaker,
    _bind_heads_to_loaded_networks,
)
from psynet.trial.create_and_rate import (
    CreateAndRateAssignmentPending,
    CreateAndRateTrialMakerMixin,
)
from psynet.trial.graph import (
    GraphChainEdge,
    GraphChainNetwork,
    GraphChainNode,
    GraphChainTrial,
    GraphChainTrialMaker,
    GraphChainVertex,
)
from psynet.trial.static import StaticNetwork, StaticNode, StaticTrial, StaticTrialMaker


class GrowthQueryTrial(ChainTrial):
    time_estimate = 1

    def make_definition(self, experiment, participant):
        return self.node.definition


class GrowthQueryStaticTrial(StaticTrial):
    time_estimate = 1


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


def create_chain_network(
    trial_maker, experiment, *, network_class=ChainNetwork, participant=None
):
    start_node = trial_maker.node_class(definition={"x": 0})
    network = network_class(
        trial_maker_id=trial_maker.id,
        start_node=start_node,
        experiment=experiment,
        chain_type=trial_maker.chain_type,
        trials_per_node=trial_maker.trials_per_node,
        target_n_nodes=trial_maker.max_nodes_per_chain,
        participant=participant,
    )
    db.session.add(network)
    db.session.flush()
    return network


def static_trial_maker(*, target_trials_per_node):
    return StaticTrialMaker(
        id_="static_growth_query",
        trial_class=GrowthQueryStaticTrial,
        nodes=[StaticNode(definition={"x": 0})],
        expected_trials_per_participant=1,
        max_trials_per_participant=1,
        target_trials_per_node=target_trials_per_node,
        balance_across_nodes=False,
    )


def initialize_trial_maker_state(trial_maker, participant):
    state = trial_maker.state_class(trial_maker, participant)
    state.participant_group = "default"
    state.participated_networks = []
    state.block_order = ["default"]
    state.set_block_position(0)
    participant.module_state = state
    db.session.add(state)
    db.session.flush()


def add_trial(
    trial_class,
    node,
    participant,
    *,
    answer=1,
    finalized=True,
    failed=False,
    propagate_failure=False,
):
    trial = trial_class(
        experiment=get_experiment(),
        node=node,
        participant=participant,
        propagate_failure=propagate_failure,
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
def test_find_chains_keeps_query_count_bounded(db_session, participant):
    exp = get_experiment()
    trial_maker = chain_trial_maker(
        chains_per_experiment=20,
        max_trials_per_participant=None,
    )
    networks = [create_chain_network(trial_maker, exp) for _ in range(20)]
    initialize_trial_maker_state(trial_maker, participant)

    # The fourth query batches viable-trial counts for every candidate head.
    with assert_query_count(min_queries=3, max_queries=4):
        eligible = trial_maker.find_chains(participant, exp)

    assert {chain.id for chain in eligible} == {chain.id for chain in networks}


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory")
def test_find_chains_batches_viable_trial_counts(db_session, participant, monkeypatch):
    import psynet.trial.chain as chain_module

    exp = get_experiment()
    trial_maker = chain_trial_maker(
        chains_per_experiment=20,
        max_trials_per_participant=None,
    )
    networks = [create_chain_network(trial_maker, exp) for _ in range(20)]
    initialize_trial_maker_state(trial_maker, participant)
    add_trial(GrowthQueryTrial, networks[0].head, participant)

    original = chain_module._count_viable_trials_for_nodes
    calls = []

    def count_once(node_ids):
        node_ids = list(node_ids)
        calls.append(node_ids)
        return original(node_ids)

    monkeypatch.setattr(chain_module, "_count_viable_trials_for_nodes", count_once)

    eligible = trial_maker.find_chains(participant, exp)

    assert len(calls) == 1
    assert set(calls[0]) == {network.head.id for network in networks}
    assert networks[0] not in eligible


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory")
def test_unlimited_static_nodes_skip_viable_trial_counts(
    db_session, participant, monkeypatch
):
    import psynet.trial.chain as chain_module

    exp = get_experiment()
    trial_maker = static_trial_maker(target_trials_per_node=None)
    networks = [
        create_chain_network(trial_maker, exp, network_class=StaticNetwork)
        for _ in range(20)
    ]
    initialize_trial_maker_state(trial_maker, participant)
    monkeypatch.setattr(
        chain_module,
        "_count_viable_trials_for_nodes",
        lambda node_ids: pytest.fail("Unlimited nodes should not query trial counts."),
    )
    participant_id = participant.id
    expected_node_ids = {network.head.id for network in networks}
    db.session.commit()
    db.session.remove()
    participant = db.session.get(Participant, participant_id)
    participant.module_state

    with assert_query_count(min_queries=2, max_queries=5):
        eligible = trial_maker.find_nodes(participant, exp)

    assert {node.id for node in eligible} == expected_node_ids
    assert "n_viable_trials" not in inspect(StaticNode).attrs
    assert StaticNode.query.filter(StaticNode.n_viable_trials == 0).count() == len(
        expected_node_ids
    )


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory")
def test_limited_static_nodes_batch_viable_trial_counts(
    db_session, participant, monkeypatch
):
    import psynet.trial.chain as chain_module

    exp = get_experiment()
    trial_maker = StaticTrialMaker(
        id_="static_growth_query",
        trial_class=GrowthQueryStaticTrial,
        nodes=[StaticNode(definition={"x": 0})],
        expected_trials_per_participant=1,
        max_trials_per_participant=None,
        target_trials_per_node=1,
    )
    networks = [
        create_chain_network(trial_maker, exp, network_class=StaticNetwork)
        for _ in range(20)
    ]
    initialize_trial_maker_state(trial_maker, participant)
    add_trial(GrowthQueryStaticTrial, networks[0].head, participant)

    original = chain_module._count_viable_trials_for_nodes
    calls = []

    def count_once(node_ids):
        node_ids = list(node_ids)
        calls.append(node_ids)
        return original(node_ids)

    monkeypatch.setattr(chain_module, "_count_viable_trials_for_nodes", count_once)
    participant_id = participant.id
    all_head_ids = {network.head.id for network in networks}
    expected_node_ids = {network.head.id for network in networks[1:]}
    db.session.commit()
    db.session.remove()
    participant = db.session.get(Participant, participant_id)
    participant.module_state

    with assert_query_count(min_queries=2, max_queries=6):
        eligible = trial_maker.find_nodes(participant, exp)

    assert len(calls) == 1
    assert set(calls[0]) == all_head_ids
    assert {node.id for node in eligible} == expected_node_ids


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory")
def test_create_and_rate_phase_queries_are_bounded(db_session, participant):
    exp = get_experiment()
    trial_maker = chain_trial_maker()
    networks = [create_chain_network(trial_maker, exp) for _ in range(20)]
    add_trial(GrowthQueryTrial, networks[0].head, participant, finalized=True)
    add_trial(GrowthQueryTrial, networks[0].head, participant, finalized=False)
    add_trial(GrowthQueryTrial, networks[1].head, participant, finalized=True)
    add_trial(GrowthQueryTrial, networks[1].head, participant, finalized=True)

    create_and_rate = object.__new__(CreateAndRateTrialMakerMixin)
    create_and_rate.creator_class = GrowthQueryTrial
    create_and_rate.rater_class = object()
    create_and_rate.n_creators = 2
    create_and_rate.wait_for_networks = False

    with assert_query_count(min_queries=2, max_queries=2):
        phases = create_and_rate.get_creation_phases(
            [network.head for network in networks]
        )

    assert phases[networks[0].head.id] == create_and_rate.WAITING_FOR_CREATORS
    assert phases[networks[1].head.id] == create_and_rate.READY_FOR_RATERS
    assert phases[networks[2].head.id] == create_and_rate.NEEDS_CREATORS

    with pytest.raises(CreateAndRateAssignmentPending, match="exit"):
        create_and_rate.get_trial_class(networks[0].head, participant, exp)
    assert (
        create_and_rate.get_trial_class(networks[1].head, participant, exp)
        is create_and_rate.rater_class
    )
    assert (
        create_and_rate.get_trial_class(networks[2].head, participant, exp)
        is create_and_rate.creator_class
    )


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory")
def test_performance_check_filters_trials_by_maker_in_sql(db_session, participant):
    exp = get_experiment()
    selected_maker = chain_trial_maker(id_="selected_performance")
    other_maker = chain_trial_maker(id_="other_performance")
    selected_network = create_chain_network(selected_maker, exp)
    other_network = create_chain_network(other_maker, exp)
    selected_trial = add_trial(
        GrowthQueryTrial,
        selected_network.head,
        participant,
    )
    for _ in range(20):
        add_trial(GrowthQueryTrial, other_network.head, participant)

    with sqlalchemy_profile(db.engine, capture_stack=True) as profiler:
        trials = selected_maker.get_participant_trials(participant)

    assert trials == [selected_trial]
    statements = profiler.get_stats(top_n=None)
    assert len(statements) == 1
    where_clause = statements[0].statement.lower().split(" where ", maxsplit=1)[1]
    assert "trial_maker_id" in where_clause


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


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory")
def test_assignment_returned_does_not_fail_within_chain_start_node(
    db_session, participant
):
    exp = get_experiment()
    within_maker = chain_trial_maker(
        id_="within_growth",
        chain_type="within",
        chains_per_participant=1,
        chains_per_experiment=None,
        recruit_mode="n_participants",
        target_n_participants=1,
    )
    network = within_maker.create_network(
        exp, participant=participant, id_within_participant=0
    )
    start_node = network.head
    assert start_node.degree == 0
    assert start_node.participant_id == participant.id

    completed = add_trial(GrowthQueryTrial, start_node, participant, finalized=True)
    incomplete = add_trial(GrowthQueryTrial, start_node, participant, finalized=False)
    db.session.commit()

    exp.assignment_returned(participant)
    db.session.commit()

    assert participant.failed
    assert "assignment_returned" in participant.failure_tags
    assert "premature_exit" in participant.failure_tags
    assert not network.failed
    assert not start_node.failed
    assert not completed.failed
    assert incomplete.failed


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory")
def test_incomplete_trial_does_not_fail_child_node(db_session, participant):
    exp = get_experiment()
    trial_maker = chain_trial_maker()
    network = create_chain_network(trial_maker, exp)
    parent = network.head
    add_trial(GrowthQueryTrial, parent, participant, finalized=True)
    db.session.commit()

    assert trial_maker.grow_network(network, exp) is True
    child = network.head
    assert child.id != parent.id

    incomplete = add_trial(
        GrowthQueryTrial,
        parent,
        participant,
        finalized=False,
        propagate_failure=True,
    )
    incomplete.fail(reason="premature_exit")
    db.session.commit()

    assert incomplete.failed
    assert not incomplete.finalized
    assert not parent.failed
    assert not child.failed
    assert not network.failed


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory")
def test_finalized_trial_fails_child_node(db_session, participant):
    exp = get_experiment()
    trial_maker = chain_trial_maker()
    network = create_chain_network(trial_maker, exp)
    parent = network.head
    finalized = add_trial(
        GrowthQueryTrial,
        parent,
        participant,
        finalized=True,
        propagate_failure=True,
    )
    db.session.commit()

    assert trial_maker.grow_network(network, exp) is True
    child = network.head
    assert child.id != parent.id

    finalized.fail(reason="performance_check")
    db.session.commit()

    assert finalized.failed
    assert child.failed
    assert not parent.failed
    assert not network.failed


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
def test_graph_finalization_fast_path_is_scoped(db_session, participant, monkeypatch):
    trial_maker = make_graph_trial_maker(
        {
            "vertices": [1, 2, 3, 4],
            "edges": [
                {"origin": 1, "target": 2},
                {"origin": 1, "target": 3},
                {"origin": 4, "target": 3},
            ],
        }
    )
    get_experiment().timeline.trial_makers[trial_maker.id] = trial_maker
    trial_maker.create_networks_across(get_experiment())
    networks = {
        n.vertex_id: n
        for n in GraphChainNetwork.query.filter_by(trial_maker_id=trial_maker.id).all()
    }
    trial = add_trial(
        GrowthQueryGraphTrial, networks[1].head, participant, finalized=False
    )
    trial.answer = 1
    trial.complete = True

    checked_network_ids = []
    grow_calls = []

    def fake_get_networks_ready_to_grow(self, network_ids=None):
        checked_network_ids.append(set(network_ids))
        return []

    def fake_call_grow_network(self, network, check_readiness=True):
        grow_calls.append((network.id, check_readiness))

    monkeypatch.setattr(
        GrowthQueryGraphTrialMaker,
        "get_networks_ready_to_grow",
        fake_get_networks_ready_to_grow,
    )
    monkeypatch.setattr(
        GrowthQueryGraphTrialMaker, "call_grow_network", fake_call_grow_network
    )

    trial.on_finalized()

    assert grow_calls == [(networks[1].id, True)]
    assert checked_network_ids == [{networks[2].id, networks[3].id}]


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


def reload_participant(participant):
    participant_id = participant.id
    db.session.commit()
    db.session.remove()
    participant = db.session.get(Participant, participant_id)
    participant.module_state
    return participant


def make_static_trial_maker(id_, *, target_trials_per_node=None, **kwargs):
    args = dict(
        id_=id_,
        trial_class=GrowthQueryStaticTrial,
        nodes=[StaticNode(definition={"x": 0})],
        expected_trials_per_participant=1,
        max_trials_per_participant=None,
        target_trials_per_node=target_trials_per_node,
        balance_across_nodes=False,
    )
    args.update(kwargs)
    return StaticTrialMaker(**args)


def create_static_networks(trial_maker, experiment, n):
    return [
        create_chain_network(trial_maker, experiment, network_class=StaticNetwork)
        for _ in range(n)
    ]


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory")
def test_static_author_hooks_do_not_n_plus_one_on_node_network(db_session, participant):
    n_nodes = 20
    exp = get_experiment()
    trial_maker = make_static_trial_maker("static_author_hooks")
    create_static_networks(trial_maker, exp, n_nodes)
    initialize_trial_maker_state(trial_maker, participant)

    def custom_node_filter(nodes, participant, experiment):
        return [node for node in nodes if node.network.failed is False]

    def select_node(nodes, participant, experiment):
        return max(nodes, key=lambda node: node.network.id)

    trial_maker.custom_node_filter = custom_node_filter
    trial_maker.select_node = select_node
    participant = reload_participant(participant)

    with assert_query_count(
        min_queries=2, max_queries=8, capture_stack=True
    ) as profiler:
        selection = trial_maker._select_trial_node(participant, exp)

    assert_no_n_plus_one(profiler, n_nodes)
    assert selection.value.network.failed is False


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory")
def test_static_prepare_trial_query_count_is_bounded(db_session, participant):
    n_nodes = 20
    exp = get_experiment()
    trial_maker = make_static_trial_maker("static_prepare_trial")
    create_static_networks(trial_maker, exp, n_nodes)
    initialize_trial_maker_state(trial_maker, participant)
    participant = reload_participant(participant)

    with assert_query_count(
        min_queries=3, max_queries=25, capture_stack=True
    ) as profiler:
        trial, status = trial_maker.prepare_trial(exp, participant)

    assert status == "available"
    assert trial is not None
    assert_no_n_plus_one(profiler, n_nodes)


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory")
def test_static_discovery_query_count_does_not_scale_with_nodes(
    db_session, participant
):
    participant_id = participant.id
    exp = get_experiment()

    def profile_find_nodes(n, maker_id):
        live = db.session.get(Participant, participant_id)
        trial_maker = make_static_trial_maker(maker_id)
        create_static_networks(trial_maker, exp, n)
        initialize_trial_maker_state(trial_maker, live)
        live = reload_participant(live)
        with sqlalchemy_profile(db.engine, capture_stack=True) as profiler:
            eligible = trial_maker.find_nodes(live, exp)
        assert len(eligible) == n
        return profiler

    small = profile_find_nodes(10, "static_scale_10")
    large = profile_find_nodes(40, "static_scale_40")
    assert large.total_count <= small.total_count + 1
    assert_no_n_plus_one(large, 40)


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory")
def test_static_discovery_keeps_public_network_counts_loaded(db_session, participant):
    exp = get_experiment()
    trial_maker = make_static_trial_maker("static_loaded_counts")
    networks = create_static_networks(trial_maker, exp, 20)
    add_trial(GrowthQueryStaticTrial, networks[0].head, participant)
    initialize_trial_maker_state(trial_maker, participant)
    participant = reload_participant(participant)

    nodes = trial_maker.find_nodes(participant, exp)

    # Selection hooks receive ORM objects and may inspect these public count
    # attributes in a loop, so discovery must not defer them into an N+1.
    with assert_query_count(max_queries=0):
        assert sorted(node.network.n_all_trials for node in nodes) == [0] * 19 + [1]


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory")
def test_bind_heads_rejects_mismatched_network_id(db_session, participant):
    exp = get_experiment()
    trial_maker = make_static_trial_maker("static_mismatched_head")
    first, second = create_static_networks(trial_maker, exp, 2)
    first.head.network_id = second.id

    with pytest.raises(RuntimeError, match="belongs to network"):
        _bind_heads_to_loaded_networks([first])


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory")
def test_bind_heads_does_not_overwrite_dirty_relationship(db_session, participant):
    exp = get_experiment()
    trial_maker = make_static_trial_maker("static_dirty_head")
    first, second = create_static_networks(trial_maker, exp, 2)
    first.head.network = second

    with db.session.no_autoflush:
        with pytest.raises(RuntimeError, match="loaded network inconsistent"):
            _bind_heads_to_loaded_networks([first])
    assert first.head.network is second
    assert inspect(first.head).attrs.network.history.has_changes()


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory")
def test_chain_author_hooks_do_not_n_plus_one_on_head_network(db_session, participant):
    n_chains = 20
    exp = get_experiment()
    trial_maker = chain_trial_maker(
        id_="chain_author_hooks",
        chains_per_experiment=n_chains,
        max_trials_per_participant=None,
    )
    for _ in range(n_chains):
        create_chain_network(trial_maker, exp)
    initialize_trial_maker_state(trial_maker, participant)

    def custom_chain_filter(chains, participant, experiment):
        return [chain for chain in chains if chain.head.network.failed is False]

    trial_maker.custom_chain_filter = custom_chain_filter
    participant = reload_participant(participant)

    with assert_query_count(
        min_queries=3, max_queries=8, capture_stack=True
    ) as profiler:
        eligible = trial_maker.find_chains(participant, exp)

    assert_no_n_plus_one(profiler, n_chains)
    assert len(eligible) == n_chains


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory")
def test_grow_readiness_does_not_load_trial_rows(db_session, participant):
    exp = get_experiment()
    trial_maker = chain_trial_maker(id_="grow_readiness_rows")
    network = create_chain_network(trial_maker, exp)
    for _ in range(20):
        add_trial(GrowthQueryTrial, network.head, participant, finalized=True)
    db.session.commit()

    with sqlalchemy_profile(db.engine, capture_stack=True) as profiler:
        assert trial_maker.network_is_ready_to_grow(network) is True

    assert profiler.total_count <= 2
    for stat in profiler.get_stats(top_n=None):
        sql = stat.statement.lower()
        if "from info" in sql and "count(" not in sql and "exists" not in sql:
            raise AssertionError(
                "Readiness check loaded trial rows instead of counting them: "
                f"{stat.statement}"
            )


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory")
def test_grow_readiness_autoflushes_uncommitted_trial_state(db_session, participant):
    exp = get_experiment()
    trial_maker = chain_trial_maker(id_="grow_readiness_autoflush")
    network = create_chain_network(trial_maker, exp)
    trial = add_trial(
        GrowthQueryTrial,
        network.head,
        participant,
        finalized=False,
    )
    trial.complete = True
    trial.finalized = True

    assert inspect(trial).attrs.finalized.history.has_changes()
    assert trial_maker.network_is_ready_to_grow(network) is True
    # The SQL readiness predicate relies intentionally on normal autoflush so
    # it sees finalization changes made earlier in the same request.
    assert not inspect(trial).attrs.finalized.history.has_changes()
