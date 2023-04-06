import psynet.experiment
from psynet.consent import (
    AudiovisualConsent,
    CAPRecruiterAudiovisualConsent,
    CAPRecruiterStandardConsent,
    DatabaseConsent,
    MainConsent,
    NoConsent,
    OpenScienceConsent,
    PrincetonCAPRecruiterConsent,
    PrincetonConsent,
    VoluntaryWithNoCompensationConsent,
)
from psynet.page import SuccessfulEndPage
from psynet.timeline import Timeline


class Exp(psynet.experiment.Experiment):
    label = "Consents demo"

    timeline = Timeline(
        NoConsent(),
        MainConsent(),
        DatabaseConsent(),
        AudiovisualConsent(),
        OpenScienceConsent(),
        VoluntaryWithNoCompensationConsent(),
        CAPRecruiterStandardConsent(),
        CAPRecruiterAudiovisualConsent(),
        PrincetonConsent(),
        PrincetonCAPRecruiterConsent(),
        SuccessfulEndPage(),
    )
