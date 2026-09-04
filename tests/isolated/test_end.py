from types import SimpleNamespace

from psynet.end import EndLogic


def _reward_html(monkeypatch, time_reward, performance_reward):
    monkeypatch.setattr(
        "psynet.utils.get_config",
        lambda: SimpleNamespace(get=lambda key, default=None: "$"),
    )
    participant = SimpleNamespace(
        time_reward=time_reward,
        performance_reward=performance_reward,
    )
    return str(EndLogic().summarize_reward(None, participant))


def test_summarize_reward_omits_zero_performance_reward(monkeypatch):
    html = _reward_html(monkeypatch, time_reward=0.12, performance_reward=0.0)
    assert (
        "You will receive a reward of <strong>$0.12</strong> for the time you spent "
        "on the experiment. " == html
    )
    assert "performance reward" not in html


def test_summarize_reward_includes_nonzero_performance_reward(monkeypatch):
    html = _reward_html(monkeypatch, time_reward=0.13, performance_reward=9.09)
    assert (
        "You will receive a reward of <strong>$0.13</strong> for the time you spent "
        "on the experiment. You have also been awarded a performance reward of "
        "<strong>$9.09</strong>. " == html
    )
    assert "!" not in html


def test_summarize_reward_treats_sub_cent_performance_reward_as_zero(monkeypatch):
    html = _reward_html(monkeypatch, time_reward=1.0, performance_reward=0.004)
    assert "performance reward" not in html
