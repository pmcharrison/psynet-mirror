import psynet.experiment
from psynet.consent import (
    AudiovisualConsent,
    DatabaseConsent,
    LabRecruiterAudiovisualConsent,
    LabRecruiterStandardConsent,
    LucidConsent,
    MainConsent,
    NoConsent,
    OpenScienceConsent,
    PrincetonConsent,
    PrincetonLabRecruiterConsent,
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
        LabRecruiterStandardConsent(),
        LabRecruiterAudiovisualConsent(),
        PrincetonConsent(),
        PrincetonLabRecruiterConsent(),
    )
