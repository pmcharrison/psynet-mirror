import os

import pytest

from psynet.participant import get_participant
from psynet.test import bot_class, next_page

PYTEST_BOT_CLASS = bot_class()


@pytest.fixture(scope="class")
def exp_dir(root):
    os.chdir(
        os.path.join(
            os.path.dirname(__file__),
            "../demos/demography/gmsi_two_modules_with_subscales",
        )
    )
    yield
    os.chdir(root)


@pytest.mark.usefixtures("exp_dir")
class TestExp(object):
    @pytest.fixture
    def demo(self, db_session):
        from psynet.demos.timeline.experiment import Exp

        instance = Exp(db_session)
        yield instance

    def test_exp_selenium(self, bot_recruits, db_session):
        for i, bot in enumerate(bot_recruits):
            driver = bot.driver

            next_page(driver, "next_button")
            next_page(driver, "1")
            next_page(driver, "1")
            next_page(driver, "1")
            next_page(driver, "1")
            next_page(driver, "7")
            next_page(driver, "1")
            next_page(driver, "1")
            next_page(driver, "next_button")
            next_page(driver, "7")
            next_page(driver, "7")
            next_page(driver, "1")
            next_page(driver, "7")
            next_page(driver, "7")
            next_page(driver, "7")
            next_page(driver, "1")

            participant = get_participant(1)
            modules = participant.modules
            assert list(modules.keys()) == ["gmsi_1", "gmsi_2"]
            assert set(list(modules["gmsi_1"].keys())) == {
                "time_started",
                "time_finished",
            }
            assert set(list(modules["gmsi_2"].keys())) == {
                "time_started",
                "time_finished",
            }
            assert len(modules["gmsi_1"]["time_started"]) == 1
            assert len(modules["gmsi_1"]["time_finished"]) == 1
            assert len(modules["gmsi_2"]["time_started"]) == 1
            assert len(modules["gmsi_2"]["time_finished"]) == 1
            assert participant.started_modules == ["gmsi_1", "gmsi_2"]
            assert participant.finished_modules == ["gmsi_1", "gmsi_2"]
            assert participant.var.gmsi_1["mean_scores_per_scale"] == {
                "Singing Abilities": 1.0,
            }
            assert participant.var.gmsi_2["mean_scores_per_scale"] == {
                "Musical Training": 7.0,
            }

            next_page(driver, "next_button", finished=True)
