import time
import uuid

import pytest
from dallinger import db

from psynet.consent import NoConsent
from psynet.experiment import get_experiment
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.participant import Participant
from psynet.pytest_psynet import path_to_demo
from psynet.timeline import Module, Timeline


def test_repeated_modules():
    with pytest.raises(
        ValueError,
        match="Duplicated module name detected: my-module",
    ):
        Timeline(
            NoConsent(),
            Module("my-module", [InfoPage("My page", time_estimate=5)]),
            Module("my-module", [InfoPage("My page", time_estimate=5)]),
            Module("my-module-2", [InfoPage("My page", time_estimate=5)]),
            Module("my-module-2", [InfoPage("My page", time_estimate=5)]),
            Module("my-module-3", [InfoPage("My page", time_estimate=5)]),
            SuccessfulEndPage(),
        )


def get_random_id():
    return str(uuid.uuid4())


@pytest.mark.parametrize(
    "experiment_directory", [path_to_demo("consents")], indirect=True
)
def test_progress_info(in_experiment_directory, db_session):
    exp = get_experiment()

    module_ids = list(exp.timeline.modules.keys())

    hit_id = get_random_id()

    participants = []
    for _ in range(100):
        participant = Participant(
            experiment=exp,
            recruiter_id="hotair",
            worker_id=get_random_id(),
            hit_id=hit_id,
            assignment_id=get_random_id(),
            mode="debug",
        )
        db.session.add(participant)
        participants.append(participant)

    db.session.commit()

    main_consent = exp.timeline.modules["main_consent"]
    audiovisual_consent = exp.timeline.modules["audiovisual_consent"]

    for i, participant in enumerate(participants):
        main_consent.start(participant)
        main_consent.end(participant)

        if i < 50:
            audiovisual_consent.start(participant)

        if i < 25:
            audiovisual_consent.end(participant)

    db.session.commit()

    start_time = time.monotonic()
    progress_info = exp._get_progress_info(module_ids)
    end_time = time.monotonic()

    time_taken = end_time - start_time

    # At the time of writing, this took about 0.1 s, but there was a big overhead from get_config.
    # We should cache get_config and thereby get the response time down.
    assert time_taken < 0.5

    assert progress_info["main_consent"]["started_n_participants"] == 100
    assert progress_info["main_consent"]["finished_n_participants"] == 100

    assert progress_info["audiovisual_consent"]["started_n_participants"] == 50
    assert progress_info["audiovisual_consent"]["finished_n_participants"] == 25
