import os
import pytest
import re
import logging
import time

from psynet.participant import Participant, get_participant
from psynet.test import bot_class, next_page

logger = logging.getLogger(__file__)
PYTEST_BOT_CLASS = bot_class()

@pytest.fixture(scope="class")
def exp_dir(root):
    os.chdir(os.path.join(os.path.dirname(__file__), "..", "psynet/demos/timeline"))
    yield
    os.chdir(root)

@pytest.mark.usefixtures("exp_dir")
class TestExp(object):

    @pytest.fixture
    def demo(self, db_session): #, exp_config):
        from psynet.demos.timeline.experiment import Exp

        instance = Exp(db_session)
        yield instance

    def test_exp_selenium(self, bot_recruits):    #two_iterations, bot_recruits):
        for i, bot in enumerate(bot_recruits):
            driver = bot.driver

            # Page 0
            time.sleep(0.2)

            assert get_participant(1).modules == {}

            assert driver.find_element_by_id("main-body").text == "Welcome to the experiment!\nNext"
            next_page(driver, "next_button")

            # Page 1
            participant = get_participant(1)
            modules = participant.modules
            assert list(modules.keys()) == ["introduction"]
            assert set(list(modules["introduction"].keys())) == {"time_started", "time_finished"}
            assert len(modules["introduction"]["time_started"]) == 1
            assert len(modules["introduction"]["time_finished"]) == 0
            assert participant.started_modules == ["introduction"]
            assert participant.finished_modules == []

            assert re.search(
                "The current time is [0-9][0-9]:[0-9][0-9]:[0-9][0-9].",
                driver.find_element_by_id("main-body").text
            )
            button = driver.find_element_by_id("next_button")
            assert button.text == "Next"
            next_page(driver, "next_button")

            # Page 2
            assert driver.find_element_by_id("main-body").text == "Write me a message!\nSubmit"
            text_input = driver.find_element_by_id("text_input")
            text_input.send_keys("Hello! I am a robot.")
            button = driver.find_element_by_id("submit_button")
            assert button.text == "Submit"
            next_page(driver, "submit_button")

            # Page 3
            assert driver.find_element_by_id("main-body").text == "Your message: Hello! I am a robot.\nNext"
            next_page(driver, "next_button")

            # Page 4
            participant = get_participant(1)
            modules = participant.modules
            assert set(list(modules.keys())) == {"chocolate", "introduction"}
            assert len(modules["introduction"]["time_started"]) == 1
            assert len(modules["introduction"]["time_finished"]) == 1
            assert len(modules["chocolate"]["time_started"]) == 1
            assert len(modules["chocolate"]["time_finished"]) == 0
            assert participant.started_modules == ["introduction", "chocolate"]
            assert participant.finished_modules == ["introduction"]

            assert driver.find_element_by_id("main-body").text == "Do you like chocolate?\nYes\nNo"
            next_page(driver, "Yes")

            # Page 5
            assert driver.find_element_by_id("main-body").text == "It's nice to hear that you like chocolate!\nNext"
            next_page(driver, "next_button")

            # Loop
            assert driver.find_element_by_id("main-body").text == "Would you like to stay in this loop?\nYes No"

            for _ in range(3):
                next_page(driver, "Yes")
                assert driver.find_element_by_id(
                    "main-body").text == "Would you like to stay in this loop?\nYes No"

            next_page(driver, "No")

            modules = get_participant(1).modules
            assert len(modules["loop"]["time_started"]) == 4
            assert len(modules["loop"]["time_finished"]) == 4

            assert driver.find_element_by_id(
                "main-body").text == "What's your favourite colour?\nRed Green Blue"
            next_page(driver, "Red")

            assert driver.find_element_by_id(
                "main-body").text == "Red is a nice colour, wait 1s.\nNext"
            next_page(driver, "next_button")

            # Final page
            assert driver.find_element_by_id("main-body").text == (
                'That\'s the end of the experiment! In addition to your base payment of $0.10, '
                'you will receive a bonus of $0.12 for the time you spent on the experiment. '
                'Thank you for taking part.\nPlease click "Finish" to complete the HIT.\nFinish'
            )

            next_page(driver, "next_button", finished=True)
