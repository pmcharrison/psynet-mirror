import pytest

from psynet.pytest_psynet import path_to_demo_experiment
from psynet.sync import SimpleSyncGroup
from psynet.utils import get_authenticated_session


@pytest.mark.parametrize(
    "experiment_directory",
    [path_to_demo_experiment("simple_sync_group")],
    indirect=True,
)
def test_sync_groups_dashboard_renders_empty_leader_as_placeholder(
    launched_experiment, db_session
):
    group = SimpleSyncGroup(
        group_type="empty-leader",
        initial_group_size=1,
        max_group_size=1,
        min_group_size=1,
        n_active_participants=0,
        accepts_top_ups=True,
    )
    db_session.add(group)
    db_session.commit()

    session = get_authenticated_session(launched_experiment.base_url)
    response = session.get(f"{launched_experiment.base_url}/dashboard/sync_groups")
    response.raise_for_status()

    row_start = response.text.index("<td>empty-leader</td>")
    empty_leader_row = response.text[
        row_start : response.text.index("</tr>", row_start)
    ]
    assert "PNone" not in response.text
    assert "—" in empty_leader_row
