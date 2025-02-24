import psynet.experiment
from psynet.consent import (
    AudiovisualConsent,
    CAPRecruiterAudiovisualConsent,
    CAPRecruiterStandardConsent,
    DatabaseConsent,
    LucidConsent,
    MainConsent,
    NoConsent,
    OpenScienceConsent,
    PrincetonCAPRecruiterConsent,
    PrincetonConsent,
    VoluntaryWithNoCompensationConsent,
)
from psynet.graphics import PrincetonLogo
from psynet.timeline import Timeline


class Exp(psynet.experiment.Experiment):
    label = "Consents demo"
    logos = [PrincetonLogo()]
    timeline = Timeline(
        NoConsent(),
        MainConsent(),
        DatabaseConsent(),
        AudiovisualConsent(),
        OpenScienceConsent(),
        VoluntaryWithNoCompensationConsent(),
        LucidConsent(),
        CAPRecruiterStandardConsent(),
        CAPRecruiterAudiovisualConsent(),
        PrincetonConsent(),
        PrincetonCAPRecruiterConsent(),
    )
