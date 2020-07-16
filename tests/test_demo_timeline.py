import os
import pytest
import re
import logging

from cached_property import cached_property
from selenium.common.exceptions import TimeoutException

logger = logging.getLogger(__file__)

from dallinger.bots import BotBase

class PYTEST_BOT_CLASS(BotBase):
    def sign_off(self):
        try:
            logger.info("Clicked submit questionnaire button.")
            self.driver.switch_to_window(self.driver.window_handles[0])
            self.driver.set_window_size(1024, 768)
            logger.info("Switched back to initial window.")
            return True
        except TimeoutException:
            logger.error("Error during experiment sign off.")
            return False

    @cached_property
    def driver(self):
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        chrome_options = Options()
        chrome_options.add_argument("--remote-debugging-port=9222")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--no-sandbox")

        # if pytestconfig.getoption('headless'):
        chrome_options.add_argument('--headless')

        return webdriver.Chrome(chrome_options=chrome_options)

import time

def next_page(driver, button_id, finished=False, poll_interval=0.25, max_wait=5.0):
    old_id = driver.execute_script("return page_uuid")
    button = driver.find_element_by_id(button_id)
    button.click()
    if finished:
        return
    waited = 0.0
    while waited < max_wait:
        time.sleep(poll_interval)
        new_id = driver.execute_script("return page_uuid")
        page_loaded = driver.execute_script("return psynet.page_loaded")
        if new_id != old_id and page_loaded:
            return
        waited += poll_interval
    raise RuntimeError(
        f"Waited for {max_wait} s but the page still hasn't loaded ("
        f"old UUID = {old_id}, "
        f"current UUID = {new_id}, "
        f"psynet.page_loaded = {page_loaded})."
    )

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

    @pytest.mark.slow
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
