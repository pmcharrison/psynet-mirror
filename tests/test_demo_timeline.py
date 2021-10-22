import logging
import os
import re
import time

import pytest

from psynet.participant import Participant, get_participant
from psynet.test import assert_text, bot_class, next_page

logger = logging.getLogger(__file__)
PYTEST_BOT_CLASS = bot_class()


@pytest.fixture(scope="class")
def exp_dir(root):
    os.chdir(os.path.join(os.path.dirname(__file__), "..", "demos/timeline"))
    yield
    os.chdir(root)


@pytest.mark.usefixtures("exp_dir")
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

            assert list(get_participant(1).modules.keys()) == [
                "cap-recruiter_standard_consent"
            ]

            driver.execute_script(
                "$('html').animate({ scrollTop: $(document).height() }, 0);"
            )
            next_page(driver, "standard_consent")

            assert_text(driver, "main-body", "Welcome to the experiment! Next")
            next_page(driver, "next_button")

            # Page 1
            participant = get_participant(1)
            modules = participant.modules
            assert list(modules.keys()) == [
                "introduction",
                "cap-recruiter_standard_consent",
            ]
            assert set(list(modules["introduction"].keys())) == {
                "time_started",
                "time_finished",
            }
            assert len(modules["introduction"]["time_started"]) == 1
            assert len(modules["introduction"]["time_finished"]) == 0
            assert participant.started_modules == [
                "cap-recruiter_standard_consent",
                "introduction",
            ]
            assert participant.finished_modules == ["cap-recruiter_standard_consent"]
            assert participant.current_module == "introduction"

            assert re.search(
                "The current time is [0-9][0-9]:[0-9][0-9]:[0-9][0-9].",
                driver.find_element_by_id("main-body").text,
            )
            button = driver.find_element_by_id("next_button")
            assert button.text == "Next"
            next_page(driver, "next_button")

            # Page 2
            assert_text(driver, "main-body", "Write me a message! Next")
            text_input = driver.find_element_by_id("text_input")
            text_input.send_keys("Hello! I am a robot.")
            assert_text(driver, "next_button", "Next")
            next_page(driver, "next_button")

            # Page 3
            assert_text(driver, "main-body", "Your message: Hello! I am a robot. Next")
            next_page(driver, "next_button")

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
            text_input = driver.find_element_by_id("number_input")
            text_input.send_keys("78.5")
            assert_text(driver, "next_button", "Next")
            next_page(driver, "next_button")

            # Page 5
            assert_text(driver, "main-body", "Your weight is 78.5 kg. Next")
            next_page(driver, "next_button")

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
            button = driver.find_element_by_id("A")
            button.click()

            button = driver.find_element_by_id("C")
            button.click()

            button = driver.find_element_by_id("A")
            button.click()

            next_page(driver, "next_button")

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
                "cap-recruiter_standard_consent",
                "chocolate",
                "weight",
                "introduction",
            }
            assert len(modules["introduction"]["time_started"]) == 1
            assert len(modules["introduction"]["time_finished"]) == 1
            assert len(modules["chocolate"]["time_started"]) == 1
            assert len(modules["chocolate"]["time_finished"]) == 0
            assert participant.started_modules == [
                "cap-recruiter_standard_consent",
                "introduction",
                "weight",
                "chocolate",
            ]
            assert participant.finished_modules == [
                "cap-recruiter_standard_consent",
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
            next_page(driver, "next_button")

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
            next_page(driver, "next_button")

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
            next_page(driver, "next_button")

            assert_text(
                driver, "main-body", "What's your favourite color? Red Green Blue"
            )
            next_page(driver, "Red")

            assert_text(driver, "main-body", "Red is a nice color, wait 1s. Next")
            next_page(driver, "next_button")

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

            next_page(driver, "next_button", finished=True)
