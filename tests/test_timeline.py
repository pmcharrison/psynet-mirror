import pytest

from psynet.consent import NoConsent
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import (
    CreditEstimate,
    MediaSpec,
    Timeline,
    join,
    switch,
    while_loop,
)
from psynet.trial.chain import (
    ChainNetwork,
    ChainNode,
    ChainSource,
    ChainTrial,
    ChainTrialMaker,
)
from psynet.utils import DuplicateKeyError


def test_merge_media_spec():
    x = MediaSpec(audio={"stim-0": "stim-0.wav"})
    y = MediaSpec(audio={"stim-1": "stim-1.wav", "stim-2": "stim-2.wav"})
    z = MediaSpec(audio={"stim-1": "stim-1.wav", "stim-2": "stim-2b.wav"})
    q = MediaSpec(audio={"stim-3": "stim-3.wav"})

    with pytest.raises(DuplicateKeyError):
        MediaSpec.merge(x, y, z).data == MediaSpec(
            audio={
                "stim-0": "stim-0.wav",
                "stim-1": "stim-1.wav",
                "stim-2": "stim-2b.wav",
            }
        )

    assert (
        MediaSpec.merge(x, y).data
        == MediaSpec(
            audio={
                "stim-0": "stim-0.wav",
                "stim-1": "stim-1.wav",
                "stim-2": "stim-2.wav",
            }
        ).data
    )

    assert (
        MediaSpec.merge(x, y, q).data
        == MediaSpec(
            audio={
                "stim-0": "stim-0.wav",
                "stim-1": "stim-1.wav",
                "stim-2": "stim-2.wav",
                "stim-3": "stim-3.wav",
            }
        ).data
    )


class CustomTrial(ChainTrial):
    time_estimate = 5


def new_trial_maker(**kwarg):
    args = dict(
        id_="test_trial_maker",
        network_class=ChainNetwork,
        node_class=ChainNode,
        source_class=ChainSource,
        trial_class=CustomTrial,
        chain_type="across",
        num_iterations_per_chain=10,
        num_trials_per_participant=5,
        num_chains_per_participant=None,
        num_chains_per_experiment=5,
        trials_per_node=1,
        balance_across_chains=True,
        check_performance_at_end=True,
        check_performance_every_trial=False,
        recruit_mode="num_trials",
        target_num_participants=None,
    )
    all_args = {**args, **kwarg}
    return ChainTrialMaker(**all_args)


def test_get_trial_maker():
    tm_1 = new_trial_maker(id_="tm-1")
    tm_2 = new_trial_maker(id_="tm-2")
    timeline = Timeline(
        NoConsent(), InfoPage("Hello", time_estimate=5), tm_1, tm_2, SuccessfulEndPage()
    )
    assert timeline.get_trial_maker("tm-1") == tm_1
    assert timeline.get_trial_maker("tm-2") == tm_2
    assert tm_1 != tm_2


def test_estimate_credit__simple():
    e = [
        InfoPage("", time_estimate=5),
        InfoPage("", time_estimate=2),
        InfoPage("", time_estimate=1),
    ]
    assert CreditEstimate(e).get_max("time") == 8


def test_estimate_credit__switch__fix_time_true():
    e = switch(
        "test",
        lambda experiment, participant: participant.var.switch,
        {
            "a": InfoPage("", time_estimate=3),
            "b": InfoPage("", time_estimate=7),
            "c": InfoPage("", time_estimate=4),
        },
    )
    assert CreditEstimate(e).get_max("time") == 7


def test_estimate_credit__switch__fix_time_false():
    e = switch(
        "test",
        lambda experiment, participant: participant.var.switch,
        {
            "a": InfoPage("", time_estimate=3),
            "b": InfoPage("", time_estimate=10),
            "c": InfoPage("", time_estimate=4),
        },
        fix_time_credit=False,
    )
    assert CreditEstimate(e).get_max("time") == 10


def test_estimate_credit__while_loop__switch__fix_time_true():
    e = while_loop(
        "loop",
        lambda experiment, participant: experiment.var.not_ready,
        switch(
            "test",
            lambda experiment, participant: participant.var.switch,
            {
                "a": InfoPage("", time_estimate=3),
                "b": InfoPage("", time_estimate=7),
                "c": InfoPage("", time_estimate=4),
            },
        ),
        expected_repetitions=3,
    )
    assert CreditEstimate(e).get_max("time") == 21


def test_estimate_credit__while_loop__switch__fix_time_false():
    e = while_loop(
        "loop",
        lambda experiment, participant: experiment.var.not_ready,
        switch(
            "test",
            lambda experiment, participant: participant.var.switch,
            {
                "a": InfoPage("", time_estimate=3),
                "b": InfoPage("", time_estimate=10),
                "c": InfoPage("", time_estimate=4),
            },
            fix_time_credit=False,
        ),
        expected_repetitions=5,
    )
    assert CreditEstimate(e).get_max("time") == 50


def test_switch_with_trial_maker():
    tm_1 = new_trial_maker(id_="tm-1")
    tm_2 = new_trial_maker(id_="tm-2")
    timeline = Timeline(
        NoConsent(),
        switch(
            "test",
            lambda experiment, participant: participant.var.switch,
            {
                "a": tm_1,
                "b": tm_2,
            },
            fix_time_credit=False,
        ),
        SuccessfulEndPage(),
    )
    assert timeline.get_trial_maker("tm-1") == tm_1
    assert timeline.get_trial_maker("tm-2") == tm_2


def test_join_1():
    page = InfoPage("Test")
    x = join(None, page, None)
    assert isinstance(x, list)
    assert len(x) == 1
    assert x[0] == page
