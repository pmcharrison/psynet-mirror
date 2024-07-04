import time

import pytest

from psynet.pytest_psynet import (
    assert_text,
    bot_class,
    click_finish_button,
    next_page,
    path_to_test_experiment,
)

PYTEST_BOT_CLASS = bot_class()


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("pickle_page")], indirect=True
)
class TestExp(object):
    def test_exp(self, bot_recruits, db_session):
        for i, bot in enumerate(bot_recruits):
            driver = bot.driver
            time.sleep(1)

            next_page(driver, "next-button")
            assert_text(
                driver, "main-body", "This page was pickled in the database. Next"
            )
            next_page(driver, "next-button")
            click_finish_button(driver)
