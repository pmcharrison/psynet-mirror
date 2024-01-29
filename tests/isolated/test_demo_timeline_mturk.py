import pytest
import requests
from dallinger import db

from psynet.experiment import Experiment
from psynet.pytest_psynet import (
    assert_text,
    bot_class,
    next_page,
    path_to_demo,
    reward_participant_page,
)

PYTEST_BOT_CLASS = bot_class()


@pytest.mark.parametrize(
    "experiment_directory", [path_to_demo("timeline_short")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestExp(object):
    def test_exp(
        self, launched_experiment, debug_server_process, bot_recruits, db_session
    ):
        from psynet.experiment import get_experiment

        for i in range(4):
            url = launched_experiment.recruiter.recruit()[0]
            bot = bot_class()(url)

            bot.participant_id = i + 1
            bot.sign_up()

            driver = bot.driver

            exp = get_experiment()
            exp.var.with_recruiter = "mturk"
            db.session.commit()

            # reward > min_accumulated_reward_for_abort (0.34 > 0.2)
            if bot.participant_id == 1:
                next_page(driver, "next-button")

                participant = Experiment.get_participant_by_id(bot.participant_id)

                assert round(participant.performance_reward) == 0
                assert round(participant.time_reward(), 2) == 0.34
                assert round(participant.calculate_reward(), 2) == 0.34

                reward_participant_page(driver, "next-button")
                assert_text(
                    driver,
                    "main-body",
                    """
                    PsyNet Your reward When you press Next, your submission will be approved. You will receive a total payment of $0.34. Finish
                    """,
                )

            # reward > min_accumulated_reward_for_abort (0.5 > 0.2) and bonus > 0 (0.16 > 0)
            if bot.participant_id == 2:
                next_page(driver, "next-button")

                participant = Experiment.get_participant_by_id(bot.participant_id)

                participant.performance_reward = 0.16
                db.session.commit()

                assert round(participant.time_reward(), 2) == 0.34
                assert round(participant.calculate_reward(), 2) == 0.50

                reward_participant_page(driver, "next-button")
                assert_text(
                    driver,
                    "main-body",
                    """
                    PsyNet Your reward When you press Next, your submission will be approved. You will receive a total payment of $0.50. It will be paid as a base payment of $0.34 and a bonus of $0.16. Finish
                    """,
                )

            # reward == min_accumulated_reward_for_abort (0.34 > 0.2)
            if bot.participant_id == 3:
                next_page(driver, "next-button")

                participant = Experiment.get_participant_by_id(bot.participant_id)

                participant.performance_reward = -0.14
                db.session.commit()

                assert round(participant.performance_reward) == 0
                assert round(participant.time_reward(), 2) == 0.34
                assert round(participant.calculate_reward(), 2) == 0.20

                reward_participant_page(driver, "next-button")
                assert_text(
                    driver,
                    "main-body",
                    """
                    PsyNet Your reward When you press Next, your submission will be approved. You will receive a total payment of $0.34. Finish
                    """,
                )

            # reward < min_accumulated_reward_for_abort (0.19 < 0.2)
            if bot.participant_id == 4:
                next_page(driver, "next-button")

                participant = Experiment.get_participant_by_id(bot.participant_id)

                participant.performance_reward = -0.15
                db.session.commit()

                assert round(participant.time_reward(), 2) == 0.34
                assert round(participant.calculate_reward(), 2) == 0.19

                reward_participant_page(driver, "next-button")
                assert_text(
                    driver,
                    "main-body",
                    """
                    PsyNet Your reward You did not complete enough of the experiment to receive a payment, sorry. Please return the HIT. Finish
                    """,
                )

            # The built-in Dallinger.complete_experiment doesn't work because it mistakenly
            # uses a GET request instead of a POST request
            requests.post(
                f"http://localhost:5000/worker_complete?participant_id={bot.participant_id}"
            )

            bot.driver.quit()
