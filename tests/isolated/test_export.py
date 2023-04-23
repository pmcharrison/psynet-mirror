import os
import tempfile
import zipfile

import dallinger
import pandas
import pytest
from click import Context

from psynet.bot import Bot
from psynet.command_line import export__local, populate_db_from_zip_file
from psynet.participant import Participant
from psynet.pytest_psynet import path_to_demo
from psynet.timeline import Response
from psynet.trial.main import Trial


@pytest.fixture(scope="session")
def data_root_dir():
    with tempfile.TemporaryDirectory() as tempdir:
        yield tempdir


@pytest.fixture
def data_dir(data_root_dir):
    return os.path.join(data_root_dir, "regular", "data")


@pytest.fixture
def database_zip_file(data_root_dir):
    return os.path.join(data_root_dir, "regular", "database.zip")


@pytest.fixture
def coin_class(experiment_module):
    return experiment_module.Coin


@pytest.mark.parametrize("experiment_directory", [path_to_demo("gibbs")], indirect=True)
@pytest.mark.usefixtures("launched_experiment")
@pytest.mark.dependency()
class TestExpWithExport:
    def test_exp_with_export(
        self,
        data_root_dir,
        data_dir,
        database_zip_file,
        coin_class,
    ):
        import time

        time.sleep(1)
        for _ in range(4):
            bot = Bot()
            bot.take_experiment()

        ctx = Context(export__local)
        ctx.invoke(export__local, path=data_root_dir, assets="none", n_parallel=None)
        # self._run_export_tests(data_root_dir, data_dir, database_zip_file, coin_class)

    #
    # def _run_export_tests(self, data_root_dir, data_dir, database_zip_file, coin_class):
    #     export_(export_path=data_root_dir, local=True, assets="none", n_parallel=None)


@pytest.mark.dependency(depends=["TestExpWithExport"])
class TestExport:
    def test_participants_file(self, data_dir):
        participants_file = os.path.join(data_dir, "Bot.csv")
        participants = pandas.read_csv(participants_file)
        nrow = participants.shape[0]
        assert nrow == 4

    def test_networks_and_trials_files(self, data_dir):
        networks_file = os.path.join(data_dir, "CustomNetwork.csv")
        networks = pandas.read_csv(networks_file)
        trials_file = os.path.join(data_dir, "CustomTrial.csv")
        trials = pandas.read_csv(trials_file)
        assert networks.shape[0] == 8
        assert not networks.failed.any()
        assert (networks.n_all_nodes == 2).all()
        assert (networks.n_alive_nodes == 2).all()
        assert (networks.n_failed_nodes == 0).all()
        assert (networks.n_failed_trials == 0).all()
        assert networks.n_all_trials.sum() == trials.shape[0]

    def test_coins_file(self, data_dir):
        coins_file = os.path.join(data_dir, "Coin.csv")
        coins = pandas.read_csv(coins_file)
        nrow = coins.shape[0]
        assert nrow == 4

    # test_coins_file(data_dir)

    # def test_prepare_db_export():
    #     json = _prepare_db_export(scrub_pii=False)
    #     assert sorted(list(json)) == [
    #         "AssetTrial",
    #         "Bot",
    #         "ChainTrialMakerState",
    #         "ChainVector",
    #         "Coin",
    #         "CustomNetwork",
    #         "CustomNode",
    #         "CustomTrial",
    #         "ExperimentAsset",
    #         "ExperimentConfig",
    #         "ModuleState",
    #         "Response",
    #         "WorkerAsyncProcess",
    #     ]
    #     # No Notification table here as bots don't produce Notifications currently
    #     assert len(json["Bot"]) == 4  # Number of participants
    #
    # test_prepare_db_export()

    def test_psynet_exports(self, data_dir):
        assert sorted(os.listdir(data_dir)) == [
            "AssetTrial.csv",
            "Bot.csv",
            "ChainTrialMakerState.csv",
            "ChainVector.csv",
            "Coin.csv",
            "CustomNetwork.csv",
            "CustomNode.csv",
            "CustomTrial.csv",
            "ExperimentAsset.csv",
            "ExperimentConfig.csv",
            "ModuleState.csv",
            # "Notification.csv",  # We don't expect any notifications to be created
            # "Recruitment.csv",  # We don't expect any recruitment
            "Response.csv",
            # "Transmission.csv",  # We don't expect any transmissions to be created
            "WorkerAsyncProcess.csv",
        ]

    # test_psynet_exports(data_dir)

    def test_experiment_feedback(self, data_dir):
        df = pandas.read_csv(os.path.join(data_dir, "Response.csv"))

        df_ = df.query("question == 'liked_experiment'")
        assert df_.shape[0] == 4
        assert list(df_.participant_id) == [1, 2, 3, 4]
        assert list(df_.answer) == ["I'm a bot so I don't really have feelings..."] * 4

        df_ = df.query("question == 'find_experiment_difficult'")
        assert df_.shape[0] == 4
        assert list(df_.participant_id) == [1, 2, 3, 4]
        assert list(df_.answer) == ["I'm a bot so I found it pretty easy..."] * 4

        df_ = df.query("question == 'encountered_technical_problems'")
        assert df_.shape[0] == 4
        assert list(df_.participant_id) == [1, 2, 3, 4]
        assert list(df_.answer) == ["No technical problems."] * 4

    # test_experiment_feedback(data_dir)

    def test_dallinger_exports(self, database_zip_file):
        with tempfile.TemporaryDirectory() as tempdir:
            with zipfile.ZipFile(database_zip_file, "r") as zip_ref:
                zip_ref.extractall(tempdir)
                dallinger_csv_files = sorted(os.listdir(os.path.join(tempdir, "data")))
                db_tables = sorted(list(dallinger.db.Base.metadata.tables.keys()))

                # Dallinger CSV files should map one-to-one to database tables
                assert dallinger_csv_files == [t + ".csv" for t in db_tables]

    # test_dallinger_exports(database_zip_file)


@pytest.mark.parametrize("experiment_directory", [path_to_demo("gibbs")], indirect=True)
@pytest.mark.usefixtures("db_session")
def test_populate_db_from_zip_file(database_zip_file, coin_class):
    """
    Here we test the process of loading the objects described in an exported zip file
    into the local database. This is an important part of the current implementation
    of data export, which works by first creating the zip file via Dallinger's export function,
    then loads it into the local database, and serializes it locally using PsyNet's
    export functions. The function relies on the zip file created in ``test_exp``;
    it would make sense to state this explicitly as a fixture, but it's proved
    to difficult to make that work in practice because of the way in which Dallinger's
    own pytest scopes have been defined.
    """
    populate_db_from_zip_file(database_zip_file)

    trials = Trial.query.all()
    assert len(trials) > 15
    assert all(t.participant_id in [1, 2, 3, 4] for t in trials)

    participants = Participant.query.all()
    assert len(participants) == 4
    assert sorted([p.id for p in participants]) == [1, 2, 3, 4]

    responses = Response.query.all()
    assert len(responses) > 15
    assert all(r.participant_id in [1, 2, 3, 4] for r in responses)

    coins = coin_class.query.all()
    assert len(coins) == 4
    assert all(c.participant_id in [1, 2, 3, 4] for c in coins)

    # test_populate_db_from_zip_file(database_zip_file, coin_class)
