import logging
import re
import time

import pytest
from selenium.webdriver.common.by import By

from psynet.participant import Participant, get_participant
from psynet.test import assert_text, bot_class, next_page

logger = logging.getLogger(__file__)
PYTEST_BOT_CLASS = bot_class()
EXPERIMENT = None


@pytest.mark.usefixtures("demo_timeline")
class TestExp(object):
    def test_variables(self, db_session):
        from psynet.utils import import_local_experiment

        exp_class = import_local_experiment()["class"]
        exp = exp_class.new(db_session)
        assert exp.var.wage_per_hour == 12.0
        assert exp.var.new_variable == "some-value"
        assert exp.var.min_accumulated_bonus_for_abort == 0.15
        assert exp.var.show_abort_button is True

    def test_exp(self, bot_recruits, db_session):  # two_iterations, bot_recruits):
        for i, bot in enumerate(bot_recruits):
            driver = bot.driver

            # Page 0
            time.sleep(1)

            assert list(get_participant(1).modules.keys()) == ["main_consent"]

            driver.execute_script(
                "$('html').animate({ scrollTop: $(document).height() }, 0);"
            )
            next_page(driver, "consent")

            assert_text(driver, "main-body", "Welcome to the experiment! Next")
            next_page(driver, "next-button")

            # Page 1
            participant = get_participant(1)
            modules = participant.modules

            assert list(modules.keys()) == [
                "main_consent",
                "introduction",
            ]
            assert set(list(modules["introduction"].keys())) == {
                "time_started",
                "time_finished",
            }
            assert len(modules["introduction"]["time_started"]) == 1
            assert len(modules["introduction"]["time_finished"]) == 0
            assert participant.started_modules == [
                "main_consent",
                "introduction",
            ]
            assert participant.finished_modules == ["main_consent"]
            assert participant.current_module == "introduction"

            assert re.search(
                "The current time is [0-9][0-9]:[0-9][0-9]:[0-9][0-9].",
                driver.find_element(By.ID, "main-body").text,
            )
            button = driver.find_element(By.ID, "next-button")
            assert button.text == "Next"
            next_page(driver, "next-button")

            # Page 2
            assert_text(driver, "main-body", "Write me a message! Next")
            text_input = driver.find_element(By.ID, "text-input")
            text_input.send_keys("Hello! I am a robot.")
            assert_text(driver, "next-button", "Next")
            next_page(driver, "next-button")

            # Page 3
            assert_text(driver, "main-body", "Your message: Hello! I am a robot. Next")
            next_page(driver, "next-button")

            db_session.commit()
            participant = Participant.query.filter_by(id=1).one()

            event_log = participant.last_response.metadata["event_log"]
            event_ids = [e["eventType"] for e in event_log]

            assert event_ids == [
                "trialConstruct",
                "trialPrepare",
                "trialStart",
                "responseEnable",
                "submitEnable",
            ]

            # Page 4
            assert_text(driver, "main-body", "What is your weight in kg? Next")
            text_input = driver.find_element(By.ID, "number-input")
            text_input.send_keys("78.5")
            assert_text(driver, "next-button", "Next")
            next_page(driver, "next-button")

            # Page 5
            assert_text(driver, "main-body", "Your weight is 78.5 kg. Next")
            next_page(driver, "next-button")

            db_session.commit()
            participant = Participant.query.filter_by(id=1).one()

            assert (
                participant.var.weight == "78.5"
            )  # ideally, NumberControl should really return a number, not a string!

            event_log = participant.last_response.metadata["event_log"]
            event_ids = [e["eventType"] for e in event_log]
            assert event_ids == [
                "trialConstruct",
                "trialPrepare",
                "trialStart",
                "responseEnable",
                "submitEnable",
            ]

            # Page 6
            button = driver.find_element(By.ID, "A")
            button.click()

            button = driver.find_element(By.ID, "C")
            button.click()

            button = driver.find_element(By.ID, "A")
            button.click()

            next_page(driver, "next-button")

            db_session.commit()
            participant = Participant.query.filter_by(id=1).one()
            buttons = [
                e["info"]["buttonId"]
                for e in participant.answer
                if e["eventType"] == "pushButtonClicked"
            ]
            assert buttons == ["A", "C", "A"]

            event_log = participant.response.metadata["event_log"]
            assert (
                len([e for e in event_log if e["eventType"] == "pushButtonClicked"])
                == 3
            )

            # Page 7
            db_session.commit()
            participant = get_participant(1)
            modules = participant.modules
            assert set(list(modules.keys())) == {
                "main_consent",
                "chocolate",
                "weight",
                "introduction",
            }
            assert len(modules["introduction"]["time_started"]) == 1
            assert len(modules["introduction"]["time_finished"]) == 1
            assert len(modules["chocolate"]["time_started"]) == 1
            assert len(modules["chocolate"]["time_finished"]) == 0
            assert participant.started_modules == [
                "main_consent",
                "introduction",
                "weight",
                "chocolate",
            ]
            assert participant.finished_modules == [
                "main_consent",
                "introduction",
                "weight",
            ]
            assert participant.current_module == "chocolate"

            assert_text(driver, "main-body", "Do you like chocolate? Yes No")
            next_page(driver, "Yes")

            # Page 8
            assert_text(
                driver, "main-body", "It's nice to hear that you like chocolate! Next"
            )
            next_page(driver, "next-button")

            # Loop
            assert_text(
                driver, "main-body", "Would you like to stay in this loop? Yes No"
            )

            for _ in range(3):
                next_page(driver, "Yes")
                assert_text(
                    driver, "main-body", "Would you like to stay in this loop? Yes No"
                )

            next_page(driver, "No")

            db_session.commit()
            modules = get_participant(1).modules
            assert len(modules["loop"]["time_started"]) == 4
            assert len(modules["loop"]["time_finished"]) == 4

            assert_text(
                driver,
                "main-body",
                "The multi-page-maker allows you to make multiple pages in one function. Each can generate its own answer. Next",
            )
            next_page(driver, "next-button")

            assert_text(
                driver, "main-body", "Participant 1, choose a shape: Square Circle"
            )
            next_page(driver, "Square")

            assert_text(
                driver, "main-body", "Participant 1, choose a chord: Major Minor"
            )
            next_page(driver, "Minor")

            assert_text(
                driver,
                "main-body",
                "If accumulate_answers is True, then the answers are stored in a list, in this case: ['Square', 'Minor']. Next",
            )
            next_page(driver, "next-button")

            assert_text(
                driver, "main-body", "What's your favourite color? Red Green Blue"
            )
            next_page(driver, "Red")

            assert_text(driver, "main-body", "Red is a nice color, wait 1s. Next")
            next_page(driver, "next-button")

            # Final page
            assert_text(
                driver,
                "main-body",
                (
                    "That's the end of the experiment! In addition to your base payment of $0.10, "
                    "you will receive a bonus of $0.36 for the time you spent on the experiment. "
                    'Thank you for taking part. Please click "Finish" to complete the HIT. Finish'
                ),
            )

            next_page(driver, "next-button", finished=True)
