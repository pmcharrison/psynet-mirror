import logging
import os
import re

from cached_property import cached_property
from dallinger.bots import BotBase
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .utils import wait_until

logger = logging.getLogger(__file__)


def assert_text(driver, element_id, value):
    element = driver.find_element(By.ID, element_id)

    def sanitize(x):
        pattern = re.compile(r"\s+")
        return re.sub(pattern, " ", x).strip()

    if sanitize(element.text) != sanitize(value):
        raise AssertionError(
            f"""
            Found some unexpected HTML text.

            Expected: {sanitize(value)}

            Found: {sanitize(element.text)}
            """
        )


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
    def get_uuid():
        return driver.execute_script("return pageUuid")

    def click_button():
        button = driver.find_element(By.ID, button_id)
        button.click()

    def is_page_ready():
        psynet_loaded = driver.execute_script(
            "try { return psynet != undefined } catch(e) { if (e instanceof ReferenceError) { return false }}"
        )
        if psynet_loaded:
            page_loaded = driver.execute_script("return psynet.pageLoaded")
            if page_loaded:
                response_enabled = driver.execute_script(
                    "return psynet.trial.events.responseEnable.happened"
                )
                if response_enabled:
                    return True
        return False

    wait_until(
        is_page_ready,
        max_wait=15.0,
        error_message="Page never became ready.",
    )

    old_uuid = get_uuid()
    click_button()
    if not finished:
        wait_until(
            lambda: is_page_ready() and get_uuid() != old_uuid,
            max_wait=10.0,
            error_message="Failed to load new page.",
        )
