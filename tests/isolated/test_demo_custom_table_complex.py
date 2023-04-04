import time

import pytest
from selenium.webdriver.common.by import By

from psynet.participant import Participant
from psynet.pytest_psynet import bot_class, next_page, path_to_demo

PYTEST_BOT_CLASS = bot_class()


@pytest.mark.parametrize(
    "experiment_directory", [path_to_demo("custom_table_complex")], indirect=True
)
class TestExp(object):
    def test_exp(self, bot_recruits, db_session, experiment_module):
        for i, bot in enumerate(bot_recruits):
            driver = bot.driver

            time.sleep(1)

            assert Participant.inherits_table
            assert not experiment_module.Pet.inherits_table
            assert experiment_module.Cat.inherits_table

            next_page(driver, "Cat")  # What kind of pet do you want?

            text_input = driver.find_element(By.ID, "text-input")
            text_input.send_keys("Geoffrey")  # What name do you want for your cat?
            next_page(driver, "next-button")

            next_page(driver, "Yes")  # Do you want a cat that hunts mice?
            next_page(driver, "next-button")
            next_page(driver, "next-button", finished=True)

            cat = experiment_module.Cat.query.one()
            assert cat.name == "Geoffrey"
            assert cat.hunts_mice

            participant = cat.participant
            assert participant.all_pets == [cat]
