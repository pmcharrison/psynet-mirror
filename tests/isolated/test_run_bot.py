import tempfile

import pytest

from psynet.bot import Bot
from psynet.db import transaction
from psynet.experiment import Request
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
        dashboard_user = config.get("dashboard_user")
        dashboard_password = config.get("dashboard_password")

        with transaction():
            bot = Bot()
            bot_id = bot.id
            bot_unique_id = bot.unique_id

        exp = launched_experiment

        with tempfile.TemporaryDirectory() as bot_tempdir:
            # The first page is a simple multiple choice question,
            # and does not have any files to upload.

            # Check the _render_page function
            assert Request.query.count() == 0
            exp._render_page(url, bot_unique_id)
            assert Request.query.count() == 1

            # Check the _fetch_bot_status_and_files function
            bot_status, bot_response_files = exp._fetch_bot_status_and_files(
                bot_id, url, dashboard_user, dashboard_password, bot_tempdir
            )
            assert bot_status["status"] == "working"
            assert bot_status["page"]["id"] == [0]
            assert bot_status["page"]["label"] == "favourite_colour"
            assert bot_status["page"]["time_estimate"] == 5
            assert bot_status["page"]["bot_response"]["answer"] == "red"
            assert len(bot_response_files) == 0

            # Check the _submit_bot_response function
            exp._submit_bot_response(url, bot_id, bot_status, bot_response_files)
