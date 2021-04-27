import logging
import os
import time

from cached_property import cached_property
from dallinger.bots import BotBase
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__file__)


def bot_class(headless=None):
    if headless is None:
        headless_env = os.getenv("HEADLESS", default="FALSE").upper()
        assert headless_env in ["TRUE", "FALSE"]
        headless = headless_env == "TRUE"

    class PYTEST_BOT_CLASS(BotBase):
        def sign_up(self):
            """Accept HIT, give consent and start experiment.

            This uses Selenium to click through buttons on the ad,
            consent, and instruction pages.
            """
            try:
                self.driver.get(self.URL)
                logger.info("Loaded ad page.")
                begin = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn-primary"))
                )
                begin.click()
                logger.info("Clicked begin experiment button.")
                WebDriverWait(self.driver, 10).until(
                    lambda d: len(d.window_handles) == 2
                )
                self.driver.switch_to.window(self.driver.window_handles[-1])
                self.driver.set_window_size(1024, 768)
                logger.info("Switched to experiment popup.")
                consent = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "consent"))
                )
                consent.click()
                logger.info("Clicked consent button.")
                return True
            except TimeoutException:
                logger.error("Error during experiment sign up.")
                return False

        def sign_off(self):
            try:
                logger.info("Clicked submit questionnaire button.")
                self.driver.switch_to.window(self.driver.window_handles[0])
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

            if headless:
                chrome_options.add_argument("--headless")

            return webdriver.Chrome(options=chrome_options)

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
