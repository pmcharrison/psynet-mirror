from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from psynet.end import UnsuccessfulEndLogic
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import (
    AsyncCodeBlock,
    CodeBlock,
    CreditEstimate,
    Elt,
    MediaSpec,
    PageMaker,
    Timeline,
    join,
    switch,
    while_loop,
)
from psynet.trial.chain import ChainNode, ChainTrial, ChainTrialMaker
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
        node_class=ChainNode,
        trial_class=CustomTrial,
        chain_type="across",
        max_nodes_per_chain=10,
        expected_trials_per_participant=5,
        max_trials_per_participant=5,
        chains_per_participant=None,
        chains_per_experiment=5,
        trials_per_node=1,
        balance_across_chains=True,
        check_performance_at_end=False,
        check_performance_every_trial=False,
        recruit_mode="n_trials",
        target_n_participants=None,
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


def test_estimate_credit__switch__bound_reward_true():
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


def test_estimate_credit__switch__bound_reward_false():
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


def test_estimate_credit__while_loop__switch__bound_reward_true():
    e = while_loop(
        "loop123",
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


def test_estimate_credit__while_loop__switch__bound_reward_false():
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
        switch(
            "test",
            lambda experiment, participant: participant.var.switch,
            {
                "a": tm_1,
                "b": tm_2,
            },
            fix_time_credit=False,
        ),
    )
    assert timeline.get_trial_maker("tm-1") == tm_1
    assert timeline.get_trial_maker("tm-2") == tm_2


def test_join_1():
    page = InfoPage("Test")
    x = join(None, page, None)
    assert isinstance(x, list)
    assert len(x) == 1
    assert x[0] == page


def test_join_accepts_list_input_with_collections():
    def background_task(participant):
        return None

    page = InfoPage("Test")
    async_block = AsyncCodeBlock(background_task, wait=False)
    joined = join([page, async_block, background_task, None])
    assert isinstance(joined, list)
    assert all(isinstance(elt, Elt) for elt in joined)
    assert not any(isinstance(elt, AsyncCodeBlock) for elt in joined)
    assert any(isinstance(elt, CodeBlock) for elt in joined)


def test_lambda_compiles_as_code_block_in_timeline():
    def my_function(participant):
        participant.var.apples = 3

    timeline = Timeline(
        my_function,
    )
    found_lambda = None
    for elt in timeline.all_elts:
        if isinstance(elt, CodeBlock):
            found_lambda = elt
            break
    assert found_lambda is not None
    assert found_lambda.function == my_function


# ---------------------------------------------------------------------------
# Timeline branch tests
# ---------------------------------------------------------------------------


def _make_mock_participant(elt_id=None):
    p = SimpleNamespace(
        elt_id=elt_id if elt_id is not None else ["main", -1],
        elt_id_max=[],
        _in_advance_page=False,
    )
    return p


class TestTimelineBranches:
    def test_default_branches_exist(self):
        t = Timeline(InfoPage("hello", time_estimate=5))
        assert "main" in t.elts
        assert "successful_end" in t.elts
        assert "unsuccessful_end" in t.elts
        assert "rejected_consent" in t.elts

    def test_main_branch_ends_with_successful_end_page(self):
        t = Timeline(InfoPage("hello", time_estimate=5))
        assert isinstance(t.elts["main"][-1], SuccessfulEndPage)

    def test_successful_end_branch_has_four_elements(self):
        t = Timeline(InfoPage("hello", time_estimate=5))
        assert len(t.elts["successful_end"]) == 4

    def test_unsuccessful_end_branch_has_four_elements(self):
        t = Timeline(InfoPage("hello", time_estimate=5))
        assert len(t.elts["unsuccessful_end"]) == 4

    def test_successful_end_branch_structure(self):
        t = Timeline(InfoPage("hello", time_estimate=5))
        branch = t.elts["successful_end"]
        assert isinstance(branch[0], CodeBlock)
        assert isinstance(branch[1], PageMaker)
        assert isinstance(branch[2], CodeBlock)
        assert isinstance(branch[3], PageMaker)

    def test_custom_branch_override(self):
        custom = UnsuccessfulEndLogic()
        t = Timeline(
            InfoPage("hello", time_estimate=5),
            unsuccessful_end=custom,
        )
        assert "unsuccessful_end" in t.elts

    def test_get_participant_branch_initial(self):
        t = Timeline(InfoPage("hello", time_estimate=5))
        p = _make_mock_participant(elt_id=["main", -1])
        assert t.get_participant_branch(p) == "main"

    def test_get_participant_branch_main(self):
        t = Timeline(InfoPage("hello", time_estimate=5))
        p = _make_mock_participant(elt_id=["main", 0])
        assert t.get_participant_branch(p) == "main"

    def test_get_participant_branch_successful_end(self):
        t = Timeline(InfoPage("hello", time_estimate=5))
        p = _make_mock_participant(elt_id=["successful_end", 0])
        assert t.get_participant_branch(p) == "successful_end"

    def test_get_participant_branch_unsuccessful_end(self):
        t = Timeline(InfoPage("hello", time_estimate=5))
        p = _make_mock_participant(elt_id=["unsuccessful_end", 0])
        assert t.get_participant_branch(p) == "unsuccessful_end"

    def test_participant_is_in_end_logic_false_for_main(self):
        t = Timeline(InfoPage("hello", time_estimate=5))
        p = _make_mock_participant(elt_id=["main", 0])
        assert not t.participant_is_in_end_logic(p)

    def test_participant_is_in_end_logic_false_for_initial(self):
        t = Timeline(InfoPage("hello", time_estimate=5))
        p = _make_mock_participant(elt_id=["main", -1])
        assert not t.participant_is_in_end_logic(p)

    def test_participant_is_in_end_logic_true_for_successful_end(self):
        t = Timeline(InfoPage("hello", time_estimate=5))
        p = _make_mock_participant(elt_id=["successful_end", 0])
        assert t.participant_is_in_end_logic(p)

    def test_participant_is_in_end_logic_true_for_unsuccessful_end(self):
        t = Timeline(InfoPage("hello", time_estimate=5))
        p = _make_mock_participant(elt_id=["unsuccessful_end", 0])
        assert t.participant_is_in_end_logic(p)

    def test_redirect_to_branch_sets_elt_id(self):
        t = Timeline(InfoPage("hello", time_estimate=5))
        p = _make_mock_participant(elt_id=["main", 0])
        t.redirect_to_branch(None, p, "unsuccessful_end")
        assert p.elt_id == ["unsuccessful_end", -1]

    def test_redirect_to_unknown_branch_raises(self):
        t = Timeline(InfoPage("hello", time_estimate=5))
        p = _make_mock_participant(elt_id=["main", 0])
        with pytest.raises(ValueError, match="Unknown timeline branch"):
            t.redirect_to_branch(None, p, "nonexistent")

    def test_pending_redirect_sets_branch(self):
        t = Timeline(InfoPage("hello", time_estimate=5))
        p = _make_mock_participant(elt_id=["main", 0])
        p.pending_redirect = "unsuccessful_end"
        # Simulate the pending redirect check at the top of advance_page
        # (full advance_page requires a real experiment context).
        pending = p.pending_redirect
        p.pending_redirect = None
        t.redirect_to_branch(None, p, pending)
        assert p.pending_redirect is None
        assert p.elt_id == ["unsuccessful_end", -1]

    def test_getitem_by_branch_name(self):
        t = Timeline(InfoPage("hello", time_estimate=5))
        assert t["main"] is t.elts["main"]
        assert t["successful_end"] is t.elts["successful_end"]

    def test_elt_ids_include_branch_name(self):
        t = Timeline(InfoPage("hello", time_estimate=5))
        first_main = t.elts["main"][0]
        assert first_main.id == ["main", 0]
        first_end = t.elts["successful_end"][0]
        assert first_end.id == ["successful_end", 0]


def _async_target(participant):
    return None


def _make_participant(stale_process=None):
    participant = MagicMock()
    participant.id = 42
    participant.awaited_async_code_block_process = stale_process
    return participant


def test_async_code_block_initiate__no_stale_process():
    block = AsyncCodeBlock(_async_target, wait=False)
    participant = _make_participant(stale_process=None)
    new_process = MagicMock(name="new_process")

    with patch("psynet.process.WorkerAsyncProcess", return_value=new_process) as ctor:
        block.initiate(participant)

    ctor.assert_called_once()
    assert participant.awaited_async_code_block_process is new_process


def test_async_code_block_initiate__raises_when_previous_process_still_pending():
    block = AsyncCodeBlock(_async_target, wait=False)
    stale = MagicMock(name="stale_process")
    stale.pending = True
    stale.failed = False
    stale.finished = False
    participant = _make_participant(stale_process=stale)

    with patch("psynet.process.WorkerAsyncProcess") as ctor:
        with pytest.raises(RuntimeError, match="already has an async code block"):
            block.initiate(participant)

    ctor.assert_not_called()
    assert participant.awaited_async_code_block_process is stale


@pytest.mark.parametrize(
    "stale_state",
    [
        {"pending": False, "finished": True, "failed": False},
        {"pending": False, "finished": False, "failed": True},
    ],
    ids=["finished", "failed"],
)
def test_async_code_block_initiate__clears_stale_finished_or_failed_process(
    stale_state, caplog
):
    block = AsyncCodeBlock(_async_target, wait=False)
    stale = MagicMock(name="stale_process", id=99, **stale_state)
    participant = _make_participant(stale_process=stale)
    new_process = MagicMock(name="new_process")

    with patch("psynet.process.WorkerAsyncProcess", return_value=new_process) as ctor:
        with caplog.at_level("WARNING"):
            block.initiate(participant)

    ctor.assert_called_once()
    assert participant.awaited_async_code_block_process is new_process
    assert any("stale reference" in record.message for record in caplog.records), (
        f"Expected a stale-reference warning, got: {[r.message for r in caplog.records]}"
    )
