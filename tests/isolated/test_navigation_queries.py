import uuid
from types import SimpleNamespace

import pytest
from dallinger import db

from psynet.experiment import get_experiment
from psynet.participant import Participant
from psynet.pytest_psynet import path_to_test_experiment
from psynet.sqlalchemy_profiling import assert_query_count
from psynet.timeline import ModuleState


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


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory")
def test_participant_request_query_loads_relationships_only_when_used(
    db_session, participant_with_module_state
):
    experiment = get_experiment()

    with assert_query_count(min_queries=1, max_queries=1):
        participant = experiment.get_participant_from_unique_id(
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
