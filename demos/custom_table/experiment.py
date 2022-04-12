from dallinger import db

import psynet.experiment
from psynet.consent import NoConsent
from psynet.data import Base, SharedMixin, show_in_dashboard
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import CodeBlock, Timeline


@show_in_dashboard
class Bird(Base, SharedMixin):
    __tablename__ = "bird"


@show_in_dashboard
class Sparrow(Bird):
    pass


def make_bird():
    x = Sparrow()
    db.session.add(x)
    db.session.commit()


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        NoConsent(),
        InfoPage("Hello!", time_estimate=1),
        CodeBlock(make_bird),
        SuccessfulEndPage(),
    )
