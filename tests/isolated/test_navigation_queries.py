import uuid
from types import SimpleNamespace

import pytest
from dallinger import db
from sqlalchemy import inspect

from psynet.experiment import get_experiment
from psynet.participant import Participant
from psynet.pytest_psynet import path_to_test_experiment
from psynet.sqlalchemy_profiling import assert_query_count
from psynet.timeline import ModuleState

pytestmark = [
    pytest.mark.parametrize(
        "experiment_directory",
        [path_to_test_experiment("timeline")],
        indirect=True,
    ),
    pytest.mark.usefixtures("in_experiment_directory"),
]


@pytest.fixture
def participant_with_module_state(db_session):
    experiment = get_experiment()
    participant = Participant(
        experiment=experiment,
        recruiter_id="hotair",
        worker_id=str(uuid.uuid4()),
        hit_id=str(uuid.uuid4()),
        assignment_id=str(uuid.uuid4()),
        mode="debug",
    )
    state = ModuleState(SimpleNamespace(id="navigation"), participant)
    state.start()
    participant.module_state = state
    db.session.add_all([participant, state])
    db.session.commit()
    unique_id = participant.unique_id
    db.session.remove()
    return unique_id


def test_participant_request_query_loads_relationships_only_when_used(
    db_session, participant_with_module_state
):
    experiment = get_experiment()

    with assert_query_count(min_queries=1, max_queries=1):
        participant = experiment._get_request_participant_from_unique_id(
            participant_with_module_state
        )

    # Request queries override collection-oriented select-in defaults. These
    # relationships remain available and each loads normally on first access.
    with assert_query_count(min_queries=1, max_queries=1):
        assert participant.module_state.module_id == "navigation"
    with assert_query_count(min_queries=1, max_queries=1):
        assert [state.module_id for state in participant._module_states] == [
            "navigation"
        ]
    with assert_query_count(min_queries=1, max_queries=1):
        assert participant.active_barriers == {}


def test_locked_request_query_keeps_relationships_unloaded(
    db_session, participant_with_module_state
):
    """Cover the locking participant load used by ``/response``."""
    experiment = get_experiment()
    participant_id = (
        experiment._get_request_participant_from_unique_id(
            participant_with_module_state
        )
    ).id

    # ``process_response`` combines the request query with row locking and
    # ``populate_existing()``. Loader options are not always honored by
    # ``Query.get()``, so assert this construct keeps them.
    with assert_query_count(min_queries=1, max_queries=1):
        participant = (
            experiment._participant_request_query()
            .with_for_update(of=Participant)
            .populate_existing()
            .get(participant_id)
        )

    unloaded = inspect(participant).unloaded
    assert {"module_state", "_module_states", "active_barriers"} <= unloaded

    with assert_query_count(min_queries=1, max_queries=1):
        assert participant.module_state.module_id == "navigation"


def test_public_participant_getter_retains_eager_relationships_when_detached(
    db_session, participant_with_module_state
):
    experiment = get_experiment()
    participant = experiment.get_participant_from_unique_id(
        participant_with_module_state
    )
    db.session.expunge(participant)

    # Public getters can be used outside request transactions, so preserve
    # their historical select-in loading behavior.
    with assert_query_count(max_queries=0):
        assert participant.module_state.module_id == "navigation"
        assert [state.module_id for state in participant._module_states] == [
            "navigation"
        ]
        assert participant.active_barriers == {}
