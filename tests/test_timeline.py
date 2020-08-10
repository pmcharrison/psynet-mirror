import pytest
from psynet.timeline import MediaSpec, Timeline
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.utils import DuplicateKeyError

from psynet.trial.chain import (
    ChainTrialMaker,
    ChainNetwork,
    ChainSource,
    ChainNode,
    ChainTrial
)


def test_merge_media_spec():
    x = MediaSpec(audio={
        "stim-0": "stim-0.wav"
    })
    y = MediaSpec(audio={
        "stim-1": "stim-1.wav",
        "stim-2": "stim-2.wav"
    })
    z = MediaSpec(audio={
        "stim-1": "stim-1.wav",
        "stim-2": "stim-2b.wav"
    })
    q = MediaSpec(audio={
        "stim-3": "stim-3.wav"
    })

    with pytest.raises(DuplicateKeyError) as e:
        MediaSpec.merge(x, y, z).data == MediaSpec(audio={
            "stim-0": "stim-0.wav",
            "stim-1": "stim-1.wav",
            "stim-2": "stim-2b.wav"
        })

    assert MediaSpec.merge(x, y).data == MediaSpec(audio={
            "stim-0": "stim-0.wav",
            "stim-1": "stim-1.wav",
            "stim-2": "stim-2.wav"
    }).data

    assert MediaSpec.merge(x, y, q).data == MediaSpec(audio={
            "stim-0": "stim-0.wav",
            "stim-1": "stim-1.wav",
            "stim-2": "stim-2.wav",
            "stim-3": "stim-3.wav"
    }).data

def new_trial_maker(**kwarg):
    args = dict(
        id_="test_trial_maker",
        network_class=ChainNetwork,
        node_class=ChainNode,
        source_class=ChainSource,
        trial_class=ChainTrial,
        phase="test",
        time_estimate_per_trial=5,
        chain_type="across",
        num_iterations_per_chain=10,
        num_trials_per_participant=5,
        num_chains_per_participant=None,
        num_chains_per_experiment=5,
        trials_per_node=1,
        active_balancing_across_chains=True,
        check_performance_at_end=True,
        check_performance_every_trial=False,
        recruit_mode="num_trials",
        target_num_participants=None
    )
    all_args = {**args, **kwarg}
    return ChainTrialMaker(**all_args)

def test_get_trial_maker():
    tm_1 = new_trial_maker(id_="tm-1")
    tm_2 = new_trial_maker(id_="tm-2")
    timeline = Timeline(
        InfoPage("Hello", time_estimate=5),
        tm_1,
        tm_2,
        SuccessfulEndPage()
    )
    assert timeline.get_trial_maker("tm-1") == tm_1
    assert timeline.get_trial_maker("tm-2") == tm_2
    assert tm_1 != tm_2
