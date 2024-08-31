import json
import time

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select

from psynet.experiment import get_and_load_config
from psynet.pytest_psynet import (
    assert_text,
    bot_class,
    click_finish_button,
    next_page,
    path_to_demo_experiment,
)

PYTEST_BOT_CLASS = bot_class()


@pytest.mark.parametrize(
    "experiment_directory", [path_to_demo_experiment("translation")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestExp(object):
    def test_variables(self, db_session):
        config = get_and_load_config()

        assert json.loads(config.get("supported_locales")) == ["en", "de", "nl"]
        assert config.get("allow_switching_locale") is True

    @pytest.mark.skip(
        reason="Skipping this test temporarily as it makes the CI fail for unknown reasons."
    )
    def test_exp(self, bot_recruits, db_session):
        for i, bot in enumerate(bot_recruits):
            driver = bot.driver

            # Page 0
            time.sleep(1)

            driver.execute_script(
                "$('html').animate({ scrollTop: $(document).height() }, 0);"
            )

            # Page 1
            assert_text(
                driver, "main-body", "Willkommen bei der Übersetzungsdemo! Weiter"
            )
            next_page(driver, "next-button")

            # Page 2
            assert_text(
                driver,
                "main-body",
                "You have chosen to translate this experiment from en to de Below you will see this text translated! Unten sehen Sie diesen Text übersetzt! Weiter",
            )

            select = Select(
                driver.find_element(By.ID, "iso-language")
            )  # Switch to Dutch
            select.select_by_visible_text("Niederländisch")
            time.sleep(1)
            assert_text(
                driver,
                "main-body",
                "You have chosen to translate this experiment from en to nl Below you will see this text translated! Hieronder ziet u deze tekst vertaald! Volgende",
            )

            select = Select(
                driver.find_element(By.ID, "iso-language")
            )  # Switch back to German
            select.select_by_visible_text("Duits")
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
            click_finish_button(driver)
