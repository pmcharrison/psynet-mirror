import json
from datetime import datetime

import pytest
import requests
from dallinger import db

from psynet.bot import Bot
from psynet.data import coerce_to_basic_types
from psynet.experiment import get_trial_maker
from psynet.participant import Participant
from psynet.pytest_psynet import path_to_demo_experiment
from psynet.trial.main import Trial, TrialNode


def test_coerce_to_basic_types():
    old = {
        "id": 1,
        "time": datetime(2020, 1, 1),
        "definition": {
            "active_index": 0,
            "vector": [1, 2, 3],
            "reverse_scale": True,
        },
    }

    new = coerce_to_basic_types(old)

    assert new == {
        "id": 1,
        "time": "2020-01-01 00:00:00.000000",
        "definition": {
            "active_index": 0,
            "vector": [1, 2, 3],
            "reverse_scale": True,
        },
    }


@pytest.mark.parametrize(
    "experiment_directory", [path_to_demo_experiment("gibbs")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestData:
    @pytest.fixture(scope="class")
    def participants(db_session, launched_experiment):
        """Create and return 2 participants for the launched experiment."""
        bots = []
        for _ in range(2):
            bot = Bot()
            db.session.add(bot)
            bots.append(bot)
            db.session.commit()

            # TODO: Update this once the rewrite-test-functions branch is merged.
            bot.take_experiment()

        return bots

    def test_participant_records(self, participants):
        data = Participant.get_records(
            [
                "id",
                "type",
                "status",
                "failed",
                "complete",
            ],
        )
        assert len(data) == 2

        for i, record in enumerate(data):
            assert record["id"] == i + 1
            assert record["type"] == "psynet.bot.Bot"
            assert record["status"] == "approved"
            assert record["failed"] is False
            assert record["complete"] is True

    @pytest.fixture
    def data(self, launched_experiment, participants):
        return launched_experiment.get_basic_data()

    def test_basic_data_is_serializable(self, data):
        json.dumps(data)

    def test_basic_data_route(self, launched_experiment, data):
        url = "http://localhost:5000/basic_data"
        url += "?dashboard_user=test_admin&dashboard_password=test_password"
        assert requests.get(url).json() == data

    def test_basic_data_participants(self, data):
        assert "participants" in data
        assert len(data["participants"]) == 2
        for i, record in enumerate(data["participants"]):
            assert record["id"] == i + 1
            assert record["complete"] is True

    def test_basic_data_nodes(self, data):
        assert "gibbs" in data
        assert "nodes" in data["gibbs"]

        records = data["gibbs"]["nodes"]
        assert isinstance(records, list)

        trial_maker = get_trial_maker("gibbs")
        assert trial_maker.chain_type == "across"

        assert len(records) == TrialNode.query.count()
        assert records[0]["id"] == 1
        assert records[0]["failed"] is False

        assert isinstance(records[0]["definition.active_index"], int)
        assert isinstance(records[0]["definition.vector"], list)

    def test_basic_data_trials(self, data):
        assert "gibbs" in data
        assert "trials" in data["gibbs"]

        records = data["gibbs"]["trials"]
        assert isinstance(records, list)

        assert len(records) == Trial.query.count()
        assert records[0]["id"] == 1
        assert records[0]["failed"] is False

        assert isinstance(records[0]["definition.active_index"], int)
        assert isinstance(records[0]["definition.vector"], list)
        assert isinstance(records[0]["definition.reverse_scale"], bool)
