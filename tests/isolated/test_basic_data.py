import pytest
from dallinger import db

from psynet.participant import Participant
from psynet.pytest_psynet import path_to_demo_experiment


@pytest.mark.parametrize(
    "experiment_directory", [path_to_demo_experiment("gibbs")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestData:
    def test_participant_records(self, launched_experiment):
        for i in range(5):
            p = Participant(
                launched_experiment,
                recruiter_id="recruiter",
                worker_id=f"worker_{i}",
                assignment_id=f"assignment_{i}",
                hit_id="hit",
                mode="debug",
            )
            db.session.add(p)
            db.session.commit()

        data = Participant.get_records(
            [
                "id",
                "type",
                "status",
                "failed",
                "complete",
            ]
        )
        assert len(data) == 5

        for i, record in enumerate(data):
            assert record["id"] == i + 1
            assert record["type"] == "psynet.participant.Participant"
            assert record["status"] == "working"
            assert record["failed"] is False
            assert record["complete"] is False
