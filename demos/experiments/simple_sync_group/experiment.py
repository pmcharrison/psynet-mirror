from typing import List

import psynet.experiment
from psynet.bot import Bot, advance_past_wait_pages
from psynet.page import InfoPage, WaitPage
from psynet.participant import Participant
from psynet.sync import GroupCloser, SimpleGrouper
from psynet.timeline import PageMaker, Timeline
from psynet.utils import get_logger

logger = get_logger()


def waiting_page(participant: Participant):
    active_barrier = participant.active_barriers.get("main_grouper", None)
    if active_barrier:
        all_participants = active_barrier.get_waiting_participants()
        all_participants.sort(key=lambda p: p.id)
        all_participant_ids = [str(participant.id) for participant in all_participants]
        content = (
            "Waiting for more participants to arrive. "
            f"IDs of currently waiting participants: {', '.join(all_participant_ids)}."
        )
    else:
        content = "Ready to go!"
    return WaitPage(content=content, wait_time=2.5)


def show_current_group():
    return PageMaker(
        lambda participant: InfoPage(
            (
                f"You are now in group {participant.sync_group.id} with participants "
                f"{', '.join(sorted([str(p.id) for p in participant.sync_group.participants], key=int))}"
            ),
        ),
        time_estimate=5,
    )


class Exp(psynet.experiment.Experiment):
    label = "Simple SyncGroup demo"

    initial_recruitment_size = 1

    timeline = Timeline(
        SimpleGrouper(
            group_type="main",
            initial_group_size=3,
            waiting_logic=PageMaker(waiting_page, time_estimate=5),
            max_wait_time=20,
        ),
        show_current_group(),
        GroupCloser(group_type="main"),
        SimpleGrouper(
            group_type="main",
            initial_group_size=2,
            waiting_logic=PageMaker(waiting_page, time_estimate=5),
            max_wait_time=20,
        ),
        show_current_group(),
    )

    test_n_bots = 6
    test_mode = "serial"

    def test_serial_run_bots(self, bots: List[Bot]):
        advance_past_wait_pages(bots)

        pages = [bot.get_current_page() for bot in bots]
        for page in pages:
            assert page.content.startswith("You are now in group")
        assert bots[0].sync_group.n_active_participants == 3
        for bot in bots:
            assert len(bot.sync_group.participants) == 3

        for bot in bots:
            bot.take_page()
        advance_past_wait_pages(bots)

        for page in pages:
            assert page.content.startswith("You are now in group")
        for bot in bots:
            assert len(bot.sync_group.participants) == 2

        for bot in bots:
            bot.run_to_completion()
