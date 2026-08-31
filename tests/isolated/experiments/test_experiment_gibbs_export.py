import os
import tempfile
from collections import Counter

import dallinger
import pandas
import pytest
from click import Context

from psynet.bot import BotDriver
from psynet.command_line import export__local, populate_db_from_zip_file
from psynet.export import load_export_table, unpack_json_column
from psynet.participant import Participant
from psynet.pytest_psynet import path_to_test_experiment
from psynet.timeline import Response
from psynet.trial.main import Trial


@pytest.fixture(scope="session")
def data_root_dir():
    with tempfile.TemporaryDirectory() as tempdir:
        yield tempdir


@pytest.fixture
def basic_data_dir(data_root_dir):
    return os.path.join(data_root_dir, "basic_data")


@pytest.fixture
def database_dir(data_root_dir):
    return os.path.join(data_root_dir, "database")


@pytest.fixture
def coin_class(experiment_module):
    return experiment_module.Coin


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("gibbs")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
@pytest.mark.dependency()
class TestExpWithExport:
    def test_exp_with_export(
        self,
        data_root_dir,
        database_dir,
        coin_class,
    ):
        import time

        time.sleep(1)
        for _ in range(6):
            bot = BotDriver()
            bot.take_experiment()

        ctx = Context(export__local)
        ctx.invoke(
            export__local,
            path=data_root_dir,
            assets="none",
            n_parallel=None,
            legacy=True,
        )


@pytest.mark.dependency(depends=["TestExpWithExport"])
class TestExport:
    def test_participants_file(self, database_dir):
        participants = load_export_table(database_dir, "participant")
        assert participants.shape[0] == 6
        # Physical COPY exports use SQLAlchemy polymorphic identity strings.
        assert (participants["type"] == "psynet.bot.Bot").all()

    def test_networks_and_trials_files(self, database_dir):
        networks = load_export_table(database_dir, "network")
        trials = load_export_table(database_dir, "trial")
        nodes = load_export_table(database_dir, "node")

        assert networks.shape[0] == 8
        assert not networks.failed.any()

        network_node_counts = Counter(nodes.network_id)
        for network_id in networks.id:
            assert network_node_counts[network_id] > 0

        assert trials.shape[0] > 0

        try:
            unpacked = unpack_json_column(trials, "definition")
            assert "active_index" in unpacked.columns
            assert "initial_index" in unpacked.columns
            assert "reverse_scale" in unpacked.columns
            assert "vector" in unpacked.columns
        except Exception as exc:
            raise ValueError(
                f"Could not unpack trial definitions from export: {exc}"
            ) from exc

    def test_coins_file(self, database_dir):
        coins = load_export_table(database_dir, "coin")
        assert coins.shape[0] == 6

    def test_basic_data_export(self, basic_data_dir):
        assert os.path.isdir(basic_data_dir)
        assert sorted(os.listdir(basic_data_dir)) == ["participant.csv", "trial.csv"]
        participants = pandas.read_csv(os.path.join(basic_data_dir, "participant.csv"))
        trials = pandas.read_csv(os.path.join(basic_data_dir, "trial.csv"))
        assert not participants.empty
        assert not trials.empty
        assert {"id", "status", "bonus"}.issubset(participants.columns)
        assert participants["id"].is_unique
        assert (participants["id"] > 0).all()
        assert not participants["status"].isna().any()
        assert not participants["bonus"].isna().any()
        assert {"id", "participant_id", "target", "answer"}.issubset(trials.columns)
        assert not trials["target"].isna().any()
        assert set(trials["target"]).issubset({"tree", "rock", "carrot", "banana"})
        assert set(trials["participant_id"]).issubset(set(participants["id"]))
        assert not trials["answer"].isna().all()

    def test_experiment_feedback(self, database_dir):
        df = load_export_table(database_dir, "response")

        df_ = df.query("question == 'liked_experiment'")
        assert df_.shape[0] == 6
        assert list(df_.participant_id) == [1, 2, 3, 4, 5, 6]
        assert list(df_.answer) == ["I'm a bot so I don't really have feelings..."] * 6

        df_ = df.query("question == 'find_experiment_difficult'")
        assert df_.shape[0] == 6
        assert list(df_.participant_id) == [1, 2, 3, 4, 5, 6]
        assert list(df_.answer) == ["I'm a bot so I found it pretty easy..."] * 6

        df_ = df.query("question == 'encountered_technical_problems'")
        assert df_.shape[0] == 6
        assert list(df_.participant_id) == [1, 2, 3, 4, 5, 6]
        assert list(df_.answer) == ["No technical problems."] * 6

    def test_database_snapshot_members(self, database_dir):
        exported_csv_files = sorted(
            name for name in os.listdir(database_dir) if name.endswith(".csv")
        )
        db_tables = sorted(list(dallinger.db.Base.metadata.tables.keys()))

        assert exported_csv_files == [t + ".csv" for t in db_tables]


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("gibbs")], indirect=True
)
@pytest.mark.usefixtures("db_session")
def test_populate_db_from_zip_file(database_dir, coin_class):
    """
    Test loading objects described in an exported archive into the local database.
    """
    populate_db_from_zip_file(database_dir)

    trials = Trial.query.all()
    assert len(trials) > 15
    assert all(t.participant_id in [1, 2, 3, 4, 5, 6] for t in trials)

    participants = Participant.query.all()
    assert len(participants) == 6
    assert sorted([p.id for p in participants]) == [1, 2, 3, 4, 5, 6]

    responses = Response.query.all()
    assert len(responses) > 15
    assert all(r.participant_id in [1, 2, 3, 4, 5, 6] for r in responses)

    coins = coin_class.query.all()
    assert len(coins) == 6
    assert all(c.participant_id in [1, 2, 3, 4, 5, 6] for c in coins)
