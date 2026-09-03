from pathlib import Path
from types import SimpleNamespace

import polib

from psynet.end import EndLogic
from psynet.utils import get_psynet_root

TIME_REWARD_MSGID = (
    "You will receive a reward of <strong>{CURRENCY}{TIME_REWARD}</strong> "
    "for the time you spent on the experiment. "
)
PERFORMANCE_REWARD_MSGID = (
    "You have also been awarded a performance reward of "
    "<strong>{CURRENCY}{PERFORMANCE_REWARD}</strong>. "
)


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


def test_reward_catalog_entries_exist_in_all_locales():
    locales_dir = Path(get_psynet_root()) / "psynet" / "locales"
    missing = []
    for po_path in sorted(locales_dir.glob("*/LC_MESSAGES/psynet.po")):
        locale = po_path.parent.parent.name
        keys = {(entry.msgctxt, entry.msgid) for entry in polib.pofile(str(po_path))}
        if ("final-page-rewards", TIME_REWARD_MSGID) not in keys:
            missing.append(f"{locale}:final-page-rewards")
        if ("final-page-performance-reward", PERFORMANCE_REWARD_MSGID) not in keys:
            missing.append(f"{locale}:final-page-performance-reward")
    assert missing == []


def test_german_time_reward_translation_omits_zero_bonus():
    po_path = (
        Path(get_psynet_root())
        / "psynet"
        / "locales"
        / "de"
        / "LC_MESSAGES"
        / "psynet.po"
    )
    po = polib.pofile(str(po_path))
    time_entry = po.find(TIME_REWARD_MSGID, msgctxt="final-page-rewards")
    assert "Leistungsprämie" not in time_entry.msgstr
    assert "{TIME_REWARD}" in time_entry.msgstr
