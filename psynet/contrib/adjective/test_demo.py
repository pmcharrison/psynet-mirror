import logging
import time

import pytest
from selenium.common.exceptions import UnexpectedAlertPresentException
from selenium.webdriver.common.by import By

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
                    if i == 0:
                        assert (
                            e.alert_text == "You need to supply at least one new tag!"
                        )
                    elif i == 1:
                        assert e.alert_text == "You need to rate all tags!"

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
                if i == 3:
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
