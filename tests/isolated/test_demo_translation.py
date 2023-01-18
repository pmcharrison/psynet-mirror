import logging
import time

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select

from psynet.pytest_psynet import assert_text, bot_class, next_page, path_to_demo

logger = logging.getLogger(__file__)
PYTEST_BOT_CLASS = bot_class()
EXPERIMENT = None


@pytest.mark.parametrize(
    "experiment_directory", [path_to_demo("translation")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestExp(object):
    def test_variables(self, db_session):
        from psynet.experiment import get_experiment

        exp = get_experiment()
        assert exp.var.supported_locales == ["en", "de", "nl"]
        assert exp.var.allow_switching_locale is True

    def test_exp(self, bot_recruits, db_session):  # two_iterations, bot_recruits):
        for i, bot in enumerate(bot_recruits):
            driver = bot.driver

            # Page 0
            time.sleep(1)

            driver.execute_script(
                "$('html').animate({ scrollTop: $(document).height() }, 0);"
            )

            # Page 1
            assert_text(
                driver, "main-body", "Willkommen bei der Übersetzungsdemo! Nächste"
            )
            next_page(driver, "next-button")

            # Page 2
            assert_text(
                driver,
                "main-body",
                "You have chosen to translate this experiment from en to de Below you will see this text translated! Unten sehen Sie diesen Text übersetzt! Nächste",
            )

            select = Select(
                driver.find_element(By.ID, "iso-language")
            )  # Switch to Dutch
            select.select_by_visible_text("Niederländisch")
            time.sleep(1)
            assert_text(
                driver,
                "main-body",
                "You have chosen to translate this experiment from en to nl Below you will see this text translated! Hieronder ziet u deze tekst vertaald! Next",
            )

            select = Select(
                driver.find_element(By.ID, "iso-language")
            )  # Switch back to German
            select.select_by_visible_text("German")
            time.sleep(1)
            next_page(driver, "next-button")

            # Page 3
            next_page(driver, "next-button")

            # Page 4
            assert_text(
                driver,
                "main-body",
                "Sie können auch Text in Drucktasten oder auf jeder Art von Seite übersetzen! Klicken Sie auf Übersetzung",
            )
            next_page(driver, "Übersetzung")

            # Page 5
            next_page(driver, "next-button", finished=True)
