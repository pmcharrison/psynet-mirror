import logging
import os

import pytest
from dallinger import db

from psynet.bot import Bot
from psynet.pytest_psynet import path_to_demo
from psynet.utils import get_logger, log_level, time_logger

pytest_plugins = ["pytest_dallinger", "pytest_psynet"]
experiment_dir = os.path.dirname(__file__)

logger = get_logger()


@pytest.mark.parametrize("experiment_directory", [path_to_demo("mcmcp")], indirect=True)
def test_experiment(launched_experiment):
    bot = Bot()

    # We allow the first page to be slowish
    with log_level(logger, logging.DEBUG), time_logger("take_page") as log:
        bot.take_page()
    assert log["time_taken"] < 2

    while True:
        with log_level(logger, logging.DEBUG), time_logger("take_page") as log:
            bot.take_page()

        # The page should load in less than 0.25 seconds
        assert log["time_taken"] < 0.25

        db.session.commit()
        if not bot.status == "working":
            break
