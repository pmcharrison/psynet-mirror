import logging
import time
import os

from cached_property import cached_property
from selenium.common.exceptions import TimeoutException
from dallinger.bots import BotBase

logger = logging.getLogger(__file__)

def bot_class(headless=None):
    if headless is None:
        headless_env = os.getenv("HEADLESS", default="FALSE")
        assert headless_env in ["TRUE", "FALSE"]
        headless = headless_env == "TRUE"

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
            # chrome_options.add_argument("--no-sandbox")

            if headless:
                chrome_options.add_argument('--headless')

            return webdriver.Chrome(chrome_options=chrome_options)
    return PYTEST_BOT_CLASS

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
