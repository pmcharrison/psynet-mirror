import time

import pytest
from selenium.webdriver.common.by import By

from psynet.pytest_psynet import assert_text, bot_class, next_page, path_to_demo

PYTEST_BOT_CLASS = bot_class()


@pytest.mark.parametrize(
    "experiment_directory", [path_to_demo("page_maker")], indirect=True
)
class TestExp:
    def test_exp(self, bot_recruits):
        for participant, bot in enumerate(bot_recruits):
            driver = bot.driver
            time.sleep(1)

            next_page(driver, "3")

            assert_text(driver, "main-body", "Page 1/3 Next")
            next_page(driver, "next-button")

            assert_text(driver, "main-body", "Page 2/3 Next")
            next_page(driver, "next-button")

            assert_text(driver, "main-body", "Page 3/3 Next")
            next_page(driver, "next-button")

            assert_text(
                driver,
                "main-body",
                "We'll now test a multi-page maker that contains a code block. Next",
            )
            next_page(driver, "next-button")

            assert_text(
                driver, "main-body", "Give me a number to multiply by 2... Next"
            )
            number_input = driver.find_element(By.ID, "number-input")
            number_input.send_keys("3")
            next_page(driver, "next-button")

            assert_text(driver, "main-body", "3 * 2 = 6 Next")
            next_page(driver, "next-button")

            assert_text(
                driver,
                "main-body",
                "We'll now test a PageMaker that contains a while loop which in turn contains a PageMaker. Next",
            )
            next_page(driver, "next-button")

            assert_text(driver, "main-body", "You are on iteration 1/3. Next")
            next_page(driver, "next-button")

            assert_text(driver, "main-body", "You are on iteration 2/3. Next")
            next_page(driver, "next-button")

            assert_text(driver, "main-body", "You are on iteration 3/3. Next")
            next_page(driver, "next-button")

            next_page(driver, "next-button", finished=True)
