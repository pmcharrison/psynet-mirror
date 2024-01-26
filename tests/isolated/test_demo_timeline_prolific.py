import pytest
import requests
from dallinger import db
from selenium.webdriver.common.by import By

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

        for i in range(6):
            url = launched_experiment.recruiter.recruit()[0]
            bot = bot_class()(url)

            bot.participant_id = i + 1
            bot.sign_up()

            driver = bot.driver

            exp = get_experiment()
            exp.var.with_recruiter = "prolific"
            db.session.commit()

            # reward == base_payment (0.34 == 0.34)
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
                    PsyNet Your reward When you press Next, your submission will be approved and you will receive the full study payment of $0.34. Finish
                    """,
                )

            # reward > participant.base_payment (0.5 > 0.34)
            if bot.participant_id == 2:
                next_page(driver, "next-button")

                participant = Experiment.get_participant_by_id(bot.participant_id)

                participant.performance_reward = 0.16
                db.session.commit()

                assert round(participant.time_reward(), 2) == 0.34
                assert round(participant.calculate_reward(), 2) == 0.5

                reward_participant_page(driver, "next-button")
                assert_text(
                    driver,
                    "main-body",
                    """
                    PsyNet Your reward When you press Next, your submission will be approved and you will receive the full study payment of $0.34. You will also receive an additional bonus of $0.16. Finish
                    """,
                )

            # reward < min_accumulated_reward_for_abort (0.19 < 0.2)
            if bot.participant_id == 3:
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
                    PsyNet Your reward You did not complete enough of the experiment to receive a payment, sorry. Please return the study. Finish
                    """,
                )

            # min_accumulated_reward_for_abort = reward < base_payment (0.2 == 0.2 < 0.34)
            if bot.participant_id == 4:
                next_page(driver, "next-button")

                participant = Experiment.get_participant_by_id(bot.participant_id)

                participant.performance_reward = -0.14
                db.session.commit()

                assert round(participant.time_reward(), 2) == 0.34
                assert round(participant.calculate_reward(), 2) == 0.2

                reward_participant_page(driver, "next-button")
                assert_text(
                    driver,
                    "main-body",
                    """
                    PsyNet Your reward You were unable to complete the experiment, but you will still be paid $0.34 for the time you put in so far.
                    When you press Next, we will pay you via the bonus mechanism. Please then return the study. Finish
                    """,
                )

            # min_accumulated_reward_for_abort < reward < base_payment (0.2 < 0.21 < 0.34)
            if bot.participant_id == 5:
                next_page(driver, "next-button")

                participant = Experiment.get_participant_by_id(bot.participant_id)

                participant.performance_reward = -0.13
                db.session.commit()

                assert round(participant.time_reward(), 2) == 0.34
                assert round(participant.calculate_reward(), 2) == 0.21

                reward_participant_page(driver, "next-button")
                assert_text(
                    driver,
                    "main-body",
                    """
                    PsyNet Your reward You were unable to complete the experiment, but you will still be paid $0.34 for the time you put in so far.
                    When you press Next, we will pay you via the bonus mechanism. Please then return the study. Finish
                    """,
                )

            if bot.participant_id == 6:
                next_page(driver, "next-button")

                participant = Experiment.get_participant_by_id(bot.participant_id)
                # lower performance reward to show "abort not possible" page
                participant.performance_reward = -0.15
                db.session.commit()

                abort_button = driver.find_element(By.ID, "abort-button")
                abort_button.click()
                driver.switch_to.window(driver.window_handles[1])

                assert_text(
                    driver,
                    "container",
                    f"""PsyNet Aborting not possible. Aborting the experiment is not possible as the experimenter does not allow it at this time!
                    You have to accumulate at least $0.20 of reward to be able to be compensated. See below information on your currently accumulated reward.
                    Study ID {participant.hit_id} Session ID {participant.assignment_id}
                    Prolific PID {participant.worker_id} Accumulated reward $0.19 Close window
                    """,
                )

                close_button = driver.find_element(By.ID, "close-button")
                close_button.click()
                driver.switch_to.window(driver.window_handles[0])

                # reset performance reward
                participant.performance_reward = 0
                db.session.commit()

                abort_button = driver.find_element(By.ID, "abort-button")
                abort_button.click()
                driver.switch_to.window(driver.window_handles[1])

                assert_text(
                    driver,
                    "container",
                    f"""PsyNet Are you sure you want to abort the experiment? If you click the Abort button, the experiment will end early,
                    and you will be automatically paid the compensation you have earned so far. Please only contact us if you have trouble
                    receiving your payment. See the information below for details of your compensation. Study ID {participant.hit_id} Session ID {participant.assignment_id}
                    Prolific PID {participant.worker_id} Accumulated reward $0.34 Close window Abort experiment
                    """,
                )

                abort_button = driver.find_element(By.ID, "abort-button")
                abort_button.click()

                assert participant.aborted is True
                assert round(participant.performance_reward, 2) == 0
                assert round(participant.time_reward(), 2) == 0.34
                assert round(participant.calculate_reward(), 2) == 0.34

            # The built-in Dallinger.complete_experiment doesn't work because it mistakenly
            # uses a GET request instead of a POST request
            requests.post(
                f"http://localhost:5000/worker_complete?participant_id={bot.participant_id}"
            )

            bot.driver.quit()
