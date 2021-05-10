import psynet.experiment
from psynet.consent import (
    CAPRecruiterAudiovisualConsentPage,
    CAPRecruiterStandardConsentPage,
    MTurkAudiovisualConsentPage,
    MTurkStandardConsentPage,
    PrincetonConsentPage,
)
from psynet.page import SuccessfulEndPage
from psynet.timeline import Timeline


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    wage_per_hour = 12.0

    timeline = Timeline(
        MTurkStandardConsentPage(),
        MTurkAudiovisualConsentPage(),
        CAPRecruiterStandardConsentPage(),
        CAPRecruiterAudiovisualConsentPage(),
        PrincetonConsentPage(),
        SuccessfulEndPage(),
    )


extra_routes = Exp().extra_routes()
