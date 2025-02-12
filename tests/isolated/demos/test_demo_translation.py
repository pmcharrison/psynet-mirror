import time

import pytest

from psynet.experiment import get_experiment
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
        exp = get_experiment()
        assert set(exp.supported_locales) == set(["en", "de", "nl"])

    def test_exp(self, bot_recruits, db_session):
        for i, bot in enumerate(bot_recruits):
            driver = bot.driver

            # Page 0
            time.sleep(1)

            # Page 1
            assert_text(driver, "main-body", "Willkommen zur Übersetzungsdemo! Weiter")
            next_page(driver, "next-button")

            # Page 2
            assert_text(
                driver,
                "main-body",
                "You have chosen to translate this experiment to de. Below you will see this text translated! Unten sehen Sie diesen Text übersetzt! Weiter",
            )

            next_page(driver, "next-button")

            # Page 3
            assert_text(
                driver,
                "main-body",
                "Here is an example of inline variable usage: Mein Name ist Alice. Mein Lieblingsessen ist pizza. Mein am wenigsten bevorzugtes Essen ist broccoli. Weiter",
            )

            next_page(driver, "next-button")

            # Page 4
            assert_text(
                driver,
                "main-body",
                "Sie können auch Text in Schaltflächen oder auf jeder Art von Seite übersetzen! Schokolade Vanille Erdbeere",
            )
            next_page(driver, "Schokolade")

            # Page 5
            assert_text(
                driver,
                "main-body",
                'Das ist das Ende des Experiments! Sie erhalten eine Belohnung von $0.05 für die Zeit, die Sie mit dem Experiment verbracht haben. Sie haben auch eine Leistungsprämie von $0.00 erhalten! Vielen Dank für Ihre Teilnahme. Bitte klicken Sie auf "Fertig", um den HIT abzuschließen. Finish',
            )

            click_finish_button(driver)
