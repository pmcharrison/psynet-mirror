from urllib.parse import parse_qs, urlparse

import pytest
from selenium.webdriver.common.by import By

from psynet.pytest_psynet import bot_class, path_to_test_experiment
from psynet.utils import wait_until

PYTEST_BOT_CLASS = bot_class()


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestExp:
    # Overview: back-navigation to /start should resume the same participant.
    def test_back_button_replays_create_participant(self, bot_recruits):
        for bot in bot_recruits:
            driver = bot.driver
            wait_until(
                lambda: "/timeline" in driver.current_url,
                max_wait=10,
                error_message="Timeline page never loaded.",
            )
            initial_unique_id = parse_qs(urlparse(driver.current_url).query).get(
                "unique_id", [None]
            )[0]
            assert initial_unique_id is not None
            wait_until(
                lambda: bool(driver.find_elements(By.ID, "consent")),
                max_wait=10,
                error_message="Timeline consent button never appeared.",
            )
            # Back navigation should revisit /start and resume the same session.
            driver.back()
            wait_until(
                lambda: "/start" in driver.current_url,
                max_wait=10,
                error_message="Back navigation did not reach the /start page.",
            )
            driver.refresh()

            wait_until(
                lambda: "/timeline" in driver.current_url,
                max_wait=10,
                error_message=(
                    "Back navigation did not resume the timeline after "
                    "the createParticipant failure."
                ),
            )
            resumed_unique_id = parse_qs(urlparse(driver.current_url).query).get(
                "unique_id", [None]
            )[0]
            assert resumed_unique_id == initial_unique_id
