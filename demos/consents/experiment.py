import psynet.experiment
from psynet.consent import (
    AudiovisualConsent,
    CAPRecruiterAudiovisualConsent,
    CAPRecruiterStandardConsent,
    DatabaseConsent,
    MainConsent,
    MTurkAudiovisualConsent,
    MTurkStandardConsent,
    NoConsent,
    OpenScienceConsent,
    PrincetonConsent,
    VoluntaryWithNoCompensationConsent,
)
from psynet.page import SuccessfulEndPage
from psynet.timeline import Timeline


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        NoConsent(),
        MainConsent(),
        DatabaseConsent(),
        AudiovisualConsent(),
        OpenScienceConsent(),
        VoluntaryWithNoCompensationConsent(),
        MTurkStandardConsent(),
        MTurkAudiovisualConsent(),
        CAPRecruiterStandardConsent(),
        CAPRecruiterAudiovisualConsent(),
        PrincetonConsent(),
        SuccessfulEndPage(),
    )
