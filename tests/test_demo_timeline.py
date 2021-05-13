import logging
import os
import re
import time

import pytest

from psynet.participant import Participant, get_participant
from psynet.test import bot_class, next_page

logger = logging.getLogger(__file__)
PYTEST_BOT_CLASS = bot_class()


@pytest.fixture(scope="class")
def exp_dir(root):
    os.chdir(os.path.join(os.path.dirname(__file__), "..", "demos/timeline"))
    yield
    os.chdir(root)


@pytest.mark.usefixtures("exp_dir")
class TestExp(object):
    @pytest.fixture
    def demo(self, db_session):  # , exp_config):
        from psynet.demos.timeline.experiment import Exp

        instance = Exp(db_session)
        yield instance

    def test_exp(self, bot_recruits, db_session):  # two_iterations, bot_recruits):
        for i, bot in enumerate(bot_recruits):
            driver = bot.driver

            # Page 0
            time.sleep(1)

            assert get_participant(1).modules == {}

            assert (
                driver.find_element_by_id("main-body").text
                == "Welcome to the experiment!\nNext"
            )
            next_page(driver, "next_button")

            # Page 1
            participant = get_participant(1)
            modules = participant.modules
            assert list(modules.keys()) == ["introduction"]
            assert set(list(modules["introduction"].keys())) == {
                "time_started",
                "time_finished",
            }
            assert len(modules["introduction"]["time_started"]) == 1
            assert len(modules["introduction"]["time_finished"]) == 0
            assert participant.started_modules == ["introduction"]
            assert participant.finished_modules == []

            assert re.search(
                "The current time is [0-9][0-9]:[0-9][0-9]:[0-9][0-9].",
                driver.find_element_by_id("main-body").text,
            )
            button = driver.find_element_by_id("next_button")
            assert button.text == "Next"
            next_page(driver, "next_button")

            # Page 2
            assert (
                driver.find_element_by_id("main-body").text
                == "Write me a message!\nNext"
            )
            text_input = driver.find_element_by_id("text_input")
            text_input.send_keys("Hello! I am a robot.")
            button = driver.find_element_by_id("next_button")
            assert button.text == "Next"
            next_page(driver, "next_button")

            # Page 3
            assert (
                driver.find_element_by_id("main-body").text
                == "Your message: Hello! I am a robot.\nNext"
            )
            next_page(driver, "next_button")

            db_session.commit()
            participant = Participant.query.filter_by(id=1).one()

            event_log = participant.last_response.metadata["event_log"]
            event_ids = [e["event_type"] for e in event_log]
            assert event_ids == [
                "init_page",
                "media_load",
                "page_load",
                "response_ready",
                "submit_ready",
                "submit_response",
            ]

            # Page 4
            assert (
                driver.find_element_by_id("main-body").text
                == "What is your weight in kg?\nNext"
            )
            text_input = driver.find_element_by_id("number_input")
            text_input.send_keys("78.5")
            button = driver.find_element_by_id("next_button")
            assert button.text == "Next"
            next_page(driver, "next_button")

            # Page 5
            assert (
                driver.find_element_by_id("main-body").text
                == "Your weight is 78.5 kg.\nNext"
            )
            next_page(driver, "next_button")

            db_session.commit()
            participant = Participant.query.filter_by(id=1).one()

            assert (
                participant.var.weight == "78.5"
            )  # ideally, NumberControl should really return a number, not a string!

            event_log = participant.last_response.metadata["event_log"]
            event_ids = [e["event_type"] for e in event_log]
            assert event_ids == [
                "init_page",
                "media_load",
                "page_load",
                "response_ready",
                "submit_ready",
                "submit_response",
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
                e["info"]["button_id"]
                for e in participant.answer
                if e["event_type"] == "push_button_clicked"
            ]
            assert buttons == ["A", "C", "A"]

            event_log = participant.response.metadata["event_log"]
            assert (
                len([e for e in event_log if e["event_type"] == "push_button_clicked"])
                == 3
            )

            # Page 7
            db_session.commit()
            participant = get_participant(1)
            modules = participant.modules
            assert set(list(modules.keys())) == {"chocolate", "weight", "introduction"}
            assert len(modules["introduction"]["time_started"]) == 1
            assert len(modules["introduction"]["time_finished"]) == 1
            assert len(modules["chocolate"]["time_started"]) == 1
            assert len(modules["chocolate"]["time_finished"]) == 0
            assert participant.started_modules == [
                "introduction",
                "weight",
                "chocolate",
            ]
            assert participant.finished_modules == ["introduction", "weight"]

            assert (
                driver.find_element_by_id("main-body").text
                == "Do you like chocolate?\nYes\nNo"
            )
            next_page(driver, "Yes")

            # Page 8
            assert (
                driver.find_element_by_id("main-body").text
                == "It's nice to hear that you like chocolate!\nNext"
            )
            next_page(driver, "next_button")

            # Loop
            assert (
                driver.find_element_by_id("main-body").text
                == "Would you like to stay in this loop?\nYes\nNo"
            )

            for _ in range(3):
                next_page(driver, "Yes")
                assert (
                    driver.find_element_by_id("main-body").text
                    == "Would you like to stay in this loop?\nYes\nNo"
                )

            next_page(driver, "No")

            db_session.commit()
            modules = get_participant(1).modules
            assert len(modules["loop"]["time_started"]) == 4
            assert len(modules["loop"]["time_finished"]) == 4

            assert (
                driver.find_element_by_id("main-body").text
                == "The multi-page-maker allows you to make multiple pages in one function. Each can generate its own answer.\nNext"
            )
            next_page(driver, "next_button")

            assert (
                driver.find_element_by_id("main-body").text
                == "Participant 1, choose a shape:\nSquare\nCircle"
            )
            next_page(driver, "Square")

            assert (
                driver.find_element_by_id("main-body").text
                == "Participant 1, choose a chord:\nMajor\nMinor"
            )
            next_page(driver, "Minor")

            assert (
                driver.find_element_by_id("main-body").text
                == "If accumulate_answers is True, then the answers are stored in a list, in this case: ['Square', 'Minor'].\nNext"
            )
            next_page(driver, "next_button")

            assert (
                driver.find_element_by_id("main-body").text
                == "What's your favourite colour?\nRed\nGreen\nBlue"
            )
            next_page(driver, "Red")

            assert (
                driver.find_element_by_id("main-body").text
                == "Red is a nice colour, wait 1s.\nNext"
            )
            next_page(driver, "next_button")

            # Final page
            assert driver.find_element_by_id("main-body").text == (
                "That's the end of the experiment! In addition to your base payment of $0.10, "
                "you will receive a bonus of $0.20 for the time you spent on the experiment. "
                'Thank you for taking part.\nPlease click "Finish" to complete the HIT.\nFinish'
            )

            next_page(driver, "next_button", finished=True)
