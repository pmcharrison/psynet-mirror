import tempfile

import pytest

from psynet.bot import Bot
from psynet.db import transaction
from psynet.pytest_psynet import path_to_test_experiment
from psynet.utils import get_config, get_experiment_url


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("run_bot")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestRunBot:
    def test_run_bot(self, launched_experiment):
        url = get_experiment_url()
        config = get_config()
        config.load()
        dashboard_user = config.get("dashboard_user")
        dashboard_password = config.get("dashboard_password")

        with transaction():
            bot = Bot()
            bot_id = bot.id
            bot_unique_id = bot.unique_id

        exp = launched_experiment

        with tempfile.TemporaryDirectory() as bot_tempdir:
            bot_status, bot_response_files = exp._fetch_bot_status_and_files(
                bot_id, url, dashboard_user, dashboard_password, bot_tempdir
            )

            import pydevd_pycharm

            pydevd_pycharm.settrace(
                "localhost", port=12345, stdoutToServer=True, stderrToServer=True
            )
