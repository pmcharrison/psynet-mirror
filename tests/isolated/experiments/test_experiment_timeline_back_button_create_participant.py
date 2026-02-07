import pytest
from selenium.webdriver.common.by import By

from psynet.pytest_psynet import assert_text, bot_class, path_to_test_experiment
from psynet.utils import wait_until

PYTEST_BOT_CLASS = bot_class()


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestExp:
    def test_back_button_replays_create_participant(self, bot_recruits):
        for bot in bot_recruits:
            driver = bot.driver
            wait_until(
                lambda: "/timeline" in driver.current_url,
                max_wait=10,
                error_message="Timeline page never loaded.",
            )
            wait_until(
                lambda: bool(driver.find_elements(By.ID, "consent")),
                max_wait=10,
                error_message="Timeline consent button never appeared.",
            )

            # Back navigation should revisit /start and re-run createParticipant.
            driver.back()

            wait_until(
                lambda: "/error-page" in driver.current_url,
                max_wait=10,
                error_message=(
                    "Back navigation did not reach the error page that follows "
                    "the createParticipant failure."
                ),
            )
            assert_text(driver, "header", "Error!")
            assert_text(
                driver,
                "error-text",
                "There has been an error and so you are unable to continue, sorry!",
            )
