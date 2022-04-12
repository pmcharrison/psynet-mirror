# This demo illustrates some simple usage of custom SQLAlchemy classes in the context of a PsyNet experiment.
# We define a new table called 'coin', and store coins in it as the experiment progresses.

from dallinger import db
from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.orm import relationship

import psynet.experiment
from psynet.consent import NoConsent
from psynet.data import Base, SharedMixin, register_table
from psynet.modular_page import PushButtonControl
from psynet.page import InfoPage, ModularPage, SuccessfulEndPage
from psynet.participant import Participant
from psynet.timeline import CodeBlock, PageMaker, Timeline, join, while_loop


@register_table
class Coin(Base, SharedMixin):
    __tablename__ = "coin"

    participant = relationship(Participant, backref="all_coins")
    participant_id = Column(Integer, ForeignKey("participant.id"))

    def __init__(self, participant):
        self.participant = participant
        self.participant_id = participant.id


def collect_coin():
    return CodeBlock(_collect_coin)


def _collect_coin(participant):
    coin = Coin(participant)
    db.session.add(coin)


def report_num_coins():
    return PageMaker(_report_num_coins, time_estimate=5)


def _report_num_coins(participant):
    coins = participant.all_coins
    num_coins = len(coins)
    return InfoPage(f"You currently have {num_coins} coin(s).", time_estimate=5)


def check_continue():
    return ModularPage(
        "check_continue",
        "Would you like to collect another coin?",
        PushButtonControl(["Yes", "No"]),
        save_answer="collecting_coins",
        time_estimate=5,
    )


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        NoConsent(),
        CodeBlock(lambda participant: participant.var.set("collecting_coins", "Yes")),
        while_loop(
            "loop",
            lambda participant: participant.var.collecting_coins == "Yes",
            logic=join(
                collect_coin(),
                report_num_coins(),
                check_continue(),
            ),
            expected_repetitions=3,
        ),
        SuccessfulEndPage(),
    )
