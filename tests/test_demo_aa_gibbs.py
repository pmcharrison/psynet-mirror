# 11 Sep 2021 - For some reason, if this test runs after `test_demo_dense_color` or after `test_demo_static`
# the following error occurs:
#
# ❯❯ Error accessing http://localhost:5000/launch (500):
# {"status": "error", "message": "Failed to load experiment in /launch: (psycopg2.errors.UniqueViolation) duplicate key value violates unique constraint \"pg_type_typname_nsp_index\"\nDETAIL:  Key (typname, typnamespace)=(participant_status, 2200) already exists.\n\n[SQL: CREATE TYPE participant_status AS ENUM ('working', 'overrecruited', 'submitted', 'approved', 'rejected', 'returned', 'abandoned', 'did_not_attend', 'bad_data', 'missing_notification', 'replaced')]\n(Background on this error at: https://sqlalche.me/e/14/gkpj)"}
# ❯❯ Experiment launch failed, check web dyno logs for details.
# ❯❯ Failed to load experiment in /launch: (psycopg2.errors.UniqueViolation) duplicate key value violates unique constraint "pg_type_typname_nsp_index"
# DETAIL:  Key (typname, typnamespace)=(participant_status, 2200) already exists.
# [SQL: CREATE TYPE participant_status AS ENUM ('working', 'overrecruited', 'submitted', 'approved', 'rejected', 'returned', 'abandoned', 'did_not_attend', 'bad_data', 'missing_notification', 'replaced')]
# (Background on this error at: https://sqlalche.me/e/14/gkpj)
#
# I have tried in vain to debug this.
# The main idea I have is that it has something to do with how PsyNet hijacks the Participant class in Dallinger.
# It therefore might be magically fixed when we fix https://gitlab.com/computational-audition-lab/psynet/-/issues/136.
#
# As a temporary fix, we have renamed the test so that it runs first out of all the demos.

import logging
import os
import shutil
import time

import pandas
import pytest

import psynet.command_line
from psynet.test import bot_class, next_page

logger = logging.getLogger(__file__)
PYTEST_BOT_CLASS = bot_class()
EXPERIMENT = None


@pytest.mark.usefixtures("demo_gibbs")
class TestExp:
    def test_exp(self, bot_recruits, db_session):
        for participant, bot in enumerate(bot_recruits):
            driver = bot.driver
            time.sleep(1)

            # What participant group would you like to join?
            participant_group = ["A", "B", "A", "B"][participant]
            next_page(driver, participant_group)

            assert (
                driver.find_element_by_id("participant-group").text
                == f"Participant group = {participant_group}"
            )

            for i in range(7):
                next_page(driver, "next-button")

            next_page(driver, "next-button")

            from psynet.participant import Participant

            pt = Participant.query.filter_by(id=participant + 1).one()
            trials = pt.trials()
            trials.sort(key=lambda x: x.id)
            network_ids = [t.network.id for t in trials]
            assert network_ids == sorted(network_ids)

            next_page(driver, "next-button", finished=True)

        self._test_export()

    def _test_export(self):
        app = "demo-app"
        psynet.command_line.export_(app=app, local=True)

        data_dir = os.path.join("data", f"data-{app}", "csv")
        participants_file = os.path.join(data_dir, "participant.csv")

        participants = pandas.read_csv(participants_file)
        nrow = participants.shape[0]
        assert nrow == 4

        shutil.rmtree("data")
