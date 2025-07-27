import tempfile

import pytest

from psynet.asset import Asset
from psynet.bot import Bot
from psynet.db import transaction
from psynet.experiment import Request
from psynet.pytest_psynet import path_to_test_experiment
from psynet.timeline import Response


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("run_bot")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestRunBot:
    def test_run_bot(self, launched_experiment):
        with transaction():
            bot = Bot()
            bot_id = bot.id
            bot_unique_id = bot.unique_id

        exp = launched_experiment

        with tempfile.TemporaryDirectory() as bot_tempdir:
            # The first page is a simple multiple choice question,
            # and does not have any files to upload.

            # Check the _render_page function
            assert Request.query.filter_by(endpoint="/timeline").count() == 0
            exp._render_page(bot_unique_id)
            assert Request.query.filter_by(endpoint="/timeline").count() == 1

            # Check the _fetch_bot_status_and_files function
            bot_status, bot_response_files = exp._fetch_bot_status_and_files(
                bot_id, bot_tempdir
            )
            assert bot_status["status"] == "working"
            assert bot_status["page"]["id"] == [0]
            assert bot_status["page"]["label"] == "favourite_colour"
            assert bot_status["page"]["time_estimate"] == 5
            assert bot_status["page"]["bot_response"]["answer"] == "red"
            assert len(bot_response_files) == 0

            # Check the _submit_bot_response function
            exp._submit_bot_response(bot_id, bot_status, bot_response_files)
            assert Response.query.count() == 1

        with tempfile.TemporaryDirectory() as bot_tempdir:
            # Check the _render_page function
            assert Request.query.filter_by(endpoint="/timeline").count() == 1
            exp._render_page(bot_unique_id)
            assert Request.query.filter_by(endpoint="/timeline").count() == 2

            # Check the _fetch_bot_status_and_files function
            bot_status, bot_response_files = exp._fetch_bot_status_and_files(
                bot_id, bot_tempdir
            )
            assert bot_status["page"]["id"] == [1]
            assert bot_status["page"]["label"] == "record_audio"
            assert bot_status["page"]["time_estimate"] == 5

            assert len(bot_response_files) == 1
            file_name = bot_response_files["audioRecording"]
            with open(file_name, "r") as f:
                assert f.read() == f"This is a recording from {bot_id}!"

            # Check the _submit_bot_response function
            assert Asset.query.count() == 0
            exp._submit_bot_response(bot_id, bot_status, bot_response_files)
            assert Response.query.count() == 2
            assert Asset.query.count() == 1
