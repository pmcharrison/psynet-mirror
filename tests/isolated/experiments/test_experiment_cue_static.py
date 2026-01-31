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
    "experiment_directory", [path_to_test_experiment("cue_static")], indirect=True
)
class TestExp:
    def test_exp(self, bot_recruits, db_session):
        for bot in bot_recruits:
            driver = bot.driver
            time.sleep(1)

            for _ in range(3):
                assert_text(driver, "main-body", "This is a custom trial")
                next_page(driver, "next-button")

            click_finish_button(driver)
