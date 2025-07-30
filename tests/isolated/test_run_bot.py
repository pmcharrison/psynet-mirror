import pytest

from psynet.asset import Asset
from psynet.bot import BotDriver
from psynet.experiment import Request
from psynet.modular_page import ModularPage
from psynet.pytest_psynet import path_to_test_experiment
from psynet.timeline import Response


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("run_bot")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestRunBot:
    def test_run_bot(self):
        bot = BotDriver()

        # The first page is a simple multiple choice question,
        # and does not have any files to upload.

        # Check the _render_page function
        # We start with one request already, because the bot driver
        # makes a request to the /timeline endpoint when it is initialized.
        assert Request.query.filter_by(endpoint="/timeline").count() == 1
        bot._render_page()
        assert Request.query.filter_by(endpoint="/timeline").count() == 2

        # Check the _fetch_status function
        bot._fetch_status()
        status = bot.status
        response_files = bot.response_files
        assert status["status"] == "working"
        assert status["page"]["id"] == [0]
        assert status["page"]["label"] == "favourite_colour"
        assert status["page"]["time_estimate"] == 5
        assert status["page"]["bot_response"]["answer"] == "red"
        assert len(response_files) == 0

        # Check the _submit_response function
        bot._submit_response(status, response_files)
        assert Response.query.count() == 1

        # The second page is an audio recording page,
        # so the bot response involves uploading a file.

        # Check the _render_page function
        assert Request.query.filter_by(endpoint="/timeline").count() == 2
        bot._render_page()
        assert Request.query.filter_by(endpoint="/timeline").count() == 3

        # Check the _fetch_status function
        bot._fetch_status()
        status = bot.status
        response_files = bot.response_files
        assert status["page"]["id"] == [1]
        assert status["page"]["label"] == "record_audio"
        assert status["page"]["time_estimate"] == 5

        assert len(response_files) == 1
        file_name = response_files["audioRecording"]
        with open(file_name, "r") as f:
            assert f.read() == f"This is a recording from {bot.id}!"

        # Check the _submit_response function
        assert Asset.query.count() == 0
        bot._submit_response(status, response_files)
        assert Response.query.count() == 2
        assert Asset.query.count() == 1

        # Third page: video recording (camera and screen)
        assert Request.query.filter_by(endpoint="/timeline").count() == 3
        bot._render_page()
        assert Request.query.filter_by(endpoint="/timeline").count() == 4

        bot._fetch_status()
        status = bot.status
        response_files = bot.response_files
        assert status["page"]["id"] == [2]
        assert status["page"]["label"] == "record_video"
        assert status["page"]["time_estimate"] == 5

        assert set(response_files.keys()) == {"cameraRecording", "screenRecording"}
        with open(response_files["cameraRecording"], "r") as f:
            assert f.read() == f"This is a camera recording from bot {bot.id}."
        with open(response_files["screenRecording"], "r") as f:
            assert f.read() == f"This is a screen recording from bot {bot.id}."

        prev_response_count = Response.query.count()
        prev_asset_count = Asset.query.count()
        bot._submit_response(status, response_files)
        assert Response.query.count() == prev_response_count + 1
        assert Asset.query.count() == prev_asset_count + 2

    def test_get_current_page(self):
        bot = BotDriver()

        # We'll just check the first page for now, should be enough
        # to ensure that the method is working.
        page = bot.get_current_page()
        assert isinstance(page, ModularPage)
        assert page.label == "favourite_colour"
