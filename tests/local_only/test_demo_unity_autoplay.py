import time

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from psynet.pytest_psynet import bot_class, next_page, path_to_demo_experiment

PYTEST_BOT_CLASS = bot_class()


@pytest.mark.parametrize(
    "experiment_directory", [path_to_demo_experiment("unity_autoplay")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestExp:
    def test_exp(self, bot_recruits, db_session):
        for participant, bot in enumerate(bot_recruits):
            driver = bot.driver
            time.sleep(1)

            driver.execute_script(
                "$('html').animate({ scrollTop: $(document).height() }, 0);"
            )

            next_page(driver, "consent")

            WebDriverWait(driver, 60).until(
                EC.element_to_be_clickable((By.ID, "next-button"))
            )
            next_page(driver, "next-button")
            next_page(driver, "next-button", finished=True)
