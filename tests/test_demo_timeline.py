import os
import pytest
import re
import logging
import time

from psynet.test import bot_class, next_page

logger = logging.getLogger(__file__)
PYTEST_BOT_CLASS = bot_class(headless=True)

@pytest.fixture(scope="class")
def exp_dir(root):
    os.chdir(os.path.join(os.path.dirname(__file__), "..", "psynet/demos/timeline"))
    yield
    os.chdir(root)

@pytest.mark.usefixtures("exp_dir")
class TestExp(object):

    # @pytest.fixture
    # def exp_config(self, active_config):
    #     from psynet.demos.timeline.experiment import extra_parameters
    #
    #     extra_parameters()
    #     active_config.set("num_participants", 3)
    #     yield active_config

    @pytest.fixture
    def demo(self, db_session): #, exp_config):
        from psynet.demos.timeline.experiment import Exp

        instance = Exp(db_session)
        yield instance

    # @pytest.fixture
    # def two_iterations(self):
    #     # Sets environment variable for debug sub-process configuration
    #     os.environ["NUM_PARTICIPANTS"] = "2"
    #     yield None
    #     del os.environ["NUM_PARTICIPANTS"]

    # def test_networks_holds_single_experiment_node(self, demo):
    #     assert len(demo.networks()) == 1
    #     assert u"experiment" == demo.networks()[0].role

    def test_exp_selenium(self, bot_recruits):    #two_iterations, bot_recruits):
        for participant, bot in enumerate(bot_recruits):
            driver = bot.driver
            time.sleep(1)
            # Page 1
            assert re.search(
                "The current time is [0-9][0-9]:[0-9][0-9]:[0-9][0-9].",
                driver.find_element_by_class_name("main_div").text
            )
            button = driver.find_element_by_id("next_button")
            assert button.text == "Next"
            next_page(driver, "next_button")

            # Page 2
            assert driver.find_element_by_class_name("main_div").text == "Write me a message!\nSubmit"
            text_input = driver.find_element_by_id("text_input")
            text_input.send_keys("Hello! I am a robot.")
            button = driver.find_element_by_id("submit_button")
            assert button.text == "Submit"
            next_page(driver, "submit_button")

            # Page 3
            assert driver.find_element_by_class_name("main_div").text == "Your message: Hello! I am a robot.\nNext"
            next_page(driver, "next_button")

            # Page 4
            assert driver.find_element_by_class_name("main_div").text == "Do you like chocolate?\nYes\nNo"
            next_page(driver, "Yes")

            # Page 5
            assert driver.find_element_by_class_name("main_div").text == "It's nice to hear that you like chocolate!\nNext"
            next_page(driver, "next_button")

            # Loop
            assert driver.find_element_by_class_name("main_div").text == "Would you like to stay in this loop?\nYes No"

            for _ in range(3):
                next_page(driver, "Yes")
                assert driver.find_element_by_class_name(
                    "main_div").text == "Would you like to stay in this loop?\nYes No"

            next_page(driver, "No")

            # Final page
            assert driver.find_element_by_class_name("main_div").text == (
                'That\'s the end of the experiment! In addition to your base payment of $0.10, '
                'you will receive a bonus of $0.10 for the time you spent on the experiment. '
                'Thank you for taking part.\nPlease click "Finish" to complete the HIT.\nFinish'
            )

            driver.find_element_by_id("next_button").click()
            # next_page(driver, "next_button", finished=True)
