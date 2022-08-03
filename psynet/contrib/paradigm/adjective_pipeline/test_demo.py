import logging
import os
import time

import pytest
from dallinger.models import Info, Participant
from selenium import webdriver
from selenium.common.exceptions import UnexpectedAlertPresentException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from psynet.participant import get_participant
from psynet.test import assert_text, bot_class, next_page

logger = logging.getLogger(__file__)
PYTEST_BOT_CLASS = bot_class()
EXPERIMENT = None


@pytest.mark.usefixtures("demo_adjective_pipeline")
class TestExp(object):
    @staticmethod
    def get_exp(db_session):
        import dallinger.experiment

        experiment_class = dallinger.experiment.load()
        return experiment_class(session=db_session)

    @staticmethod
    def finalize_all_networks(db_session):
        exp = TestExp.get_exp(db_session)
        for network in exp.networks():
            network.full = True
            db_session.commit()

    @staticmethod
    def submit_new_tag(driver, tag):
        text_input = driver.find_element(By.CLASS_NAME, "tt-input")
        text_input.send_keys(f"{tag}\n")

    @staticmethod
    def click_next(driver, _id="next-button", finished=False):
        driver.execute_script(
            "$('html').animate({ scrollTop: $(document).height() }, 0);"
        )
        next_page(driver, _id, finished)

    def test_single_video(self, bot_recruits, db_session, experiment_module):
        for i, bot in enumerate(bot_recruits):
            driver = bot.driver
            # Page 0
            time.sleep(1)

            assert list(get_participant(i + 1).modules.keys()) == ["test"]
            assert_text(driver, "Single video", "Single video")
            self.click_next(driver, _id="Single video")
            time.sleep(1)
            if i == 0:
                # TEST1: Try to continue without entering an initial tag √
                try:
                    self.click_next(driver, _id="next_button")
                except UnexpectedAlertPresentException as e:
                    assert e.alert_text == "You need to supply at least one new tag!"

                # View stimulus
                self.submit_new_tag(driver, "a")
                self.submit_new_tag(driver, "b")
                self.click_next(driver, _id="next_button")
                time.sleep(1)

                # Bonus page
                main = driver.find_element(By.ID, "main-body")
                main.text.startswith('You just unlocked an entirely new word: "a"')
                participant = get_participant(i + 1)
                # TEST2 Check if participant get's paid a bonus every iteration (show_positive_feedback_every=1)
                assert (
                    participant.performance_bonus == 0.03
                )  # 0.02 for the new tag (2*9*4/60^2) + 0.01 unlocked bonus
                self.click_next(driver)
                self.click_next(driver, finished=True)
            else:
                # Mark rate tags as 5
                for elem in driver.find_elements(By.CLASS_NAME, "rating5"):
                    elem.click()
                self.submit_new_tag(driver, chr(99 + i))
                self.click_next(driver, _id="next_button")
                self.click_next(driver)
                if i == 4:
                    # TEST3: Check early convergence
                    assert (
                        self.get_exp(db_session)
                        .timeline.get_trial_maker("single_video_trial")
                        .networks[0]
                        .full
                    )
                    # Stop recruiting
                    self.finalize_all_networks(db_session)
                self.click_next(driver, finished=True)

    @staticmethod
    def rate_all_and_continue(driver, rating):
        for elem in driver.find_elements(By.CLASS_NAME, rating):
            elem.click()
        while not driver.find_element(By.ID, "next_button").is_enabled():
            time.sleep(0.1)
        TestExp.click_next(driver, _id="next_button")
        time.sleep(1)

    def test_mixed_media(self, bot_recruits, db_session, experiment_module):
        # Check:
        # - TEST4 are the networks pre-populated correctly?
        exp = self.get_exp(db_session)
        prepop = exp.timeline.get_trial_maker(
            "mixed_media_practice_trial"
        ).prepopulate_networks
        assert all(
            [
                network.definition["initial_tags"] in prepop
                for network in exp.timeline.get_trial_maker(
                    "mixed_media_practice_trial"
                ).networks
            ]
        )
        for i, bot in enumerate(bot_recruits):
            driver = bot.driver
            # Page 0
            time.sleep(1)

            assert list(get_participant(i + 1).modules.keys()) == ["test"]
            assert_text(driver, "Mixed media practice", "Mixed media practice")
            self.click_next(driver, _id="Mixed media practice")
            time.sleep(4)
            # TEST5: Try to continuing without rating all existent tags
            try:
                self.click_next(driver, _id="next_button")
            except UnexpectedAlertPresentException as e:
                assert e.alert_text == "You need to rate all tags!"
            ratings = [f"rating{i}" for i in range(3, 6)]
            for rating in ratings:
                self.rate_all_and_continue(driver, rating)

            for rating in reversed(ratings):
                self.rate_all_and_continue(driver, rating)

            self.finalize_all_networks(db_session)
            participant = get_participant(i + 1)
            # TEST6: Make sure people are kicked out of the practice if they are inconsistent
            assert participant.failed
            self.click_next(driver, finished=True)

    @staticmethod
    def new_driver(driver):
        trimmed_url = driver.current_url.split("?")[0]
        old_page = os.path.basename(trimmed_url)
        url = (
            trimmed_url.replace(old_page, "")
            + "ad?generate_tokens=true&recruiter=hotair"
        )
        chrome_options = Options()
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--no-sandbox")
        headless_env = os.getenv("HEADLESS", default="FALSE").upper()
        assert headless_env in ["TRUE", "FALSE"]

        if headless_env == "TRUE":
            chrome_options.add_argument("--headless")

        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)
        logger.info("Loaded ad page.")
        begin = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn-primary"))
        )
        begin.click()
        logger.info("Clicked begin experiment button.")
        WebDriverWait(driver, 10).until(lambda d: len(d.window_handles) == 2)
        driver.switch_to.window(driver.window_handles[-1])
        driver.set_window_size(1024, 768)
        logger.info("Switched to experiment popup.")
        consent = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "consent"))
        )
        consent.click()
        logger.info("Clicked consent button.")
        return driver

    def test_multiple_images(self, bot_recruits, db_session, experiment_module):
        for i, bot in enumerate(bot_recruits):
            if i == 0:
                driver = bot.driver
                # Page 0
                time.sleep(1)

                assert_text(driver, "Multiple images", "Multiple images")
                self.click_next(driver, _id="Multiple images")

                for _ in range(3):
                    self.submit_new_tag(driver, "flag me")
                    self.click_next(driver, _id="next_button")

                # Open second participant
                driver2 = self.new_driver(driver)
                self.click_next(driver2, _id="Multiple images")
                for _ in range(3):  # 3 cause driver1 blocks one
                    elements = driver2.find_elements(By.CLASS_NAME, "flag")
                    if len(elements) > 0:
                        for elem in elements:
                            elem.click()
                    else:
                        self.submit_new_tag(driver2, "test")
                    self.click_next(driver2, _id="next_button")

                self.submit_new_tag(driver, "test2")
                self.click_next(driver, _id="next_button")
                error_page = driver.find_element(By.ID, "main-body").text
                assert "You will now be excluded from the experiment" in error_page
                assert (
                    len(error_page.split("flagged your label")) - 1 == 3
                )  # 3 cause 3 creations were made
                self.click_next(driver)

                # TEST7 Make sure people are kicked out of the experiment if they give at least two tags that are flagged
                assert (
                    "Unfortunately the experiment must end early."
                    in driver.find_element(By.ID, "main-body").text
                )

                self.click_next(driver2, _id="next-button", finished=True)

                driver3 = self.new_driver(driver)
                self.click_next(driver3, _id="Multiple images")
                for _ in range(4):
                    elements = driver3.find_elements(By.CLASS_NAME, "flag")
                    for elem in elements:
                        elem.click()
                    self.click_next(driver3, _id="next_button")
                self.click_next(driver3, _id="next-button", finished=True)

                driver4 = self.new_driver(driver)
                self.click_next(driver4, _id="Multiple images")
                for _ in range(4):
                    elements = driver4.find_elements(By.CLASS_NAME, "rating5")
                    for elem in elements:
                        elem.click()
                    self.submit_new_tag(driver4, "flag me")
                    self.click_next(driver4, _id="next_button")
                    time.sleep(0.5)
                    answer = Info.query.order_by(Info.id).all()[-2].answer

                    # TEST8 Test if tag pruning works correctly
                    assert answer["new_tags"] == ["flag me"]

                    # TEST9 The same tag can reappear
                    assert "flag me" not in answer["tags"]

                self.finalize_all_networks(db_session)

                # Manually set all participants to approved
                for participant in Participant.query.filter_by(status="working").all():
                    get_participant(participant.id).status = "approved"
                    db_session.commit()
                logger.info("Experiment completed")
                self.click_next(driver, _id="next-button", finished=True)
                self.click_next(driver4, _id="next-button", finished=True)
