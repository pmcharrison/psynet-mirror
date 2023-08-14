# pylint: disable=unused-import,abstract-method,unused-argument,no-member

import psynet.experiment
from psynet.consent import NoConsent
from psynet.page import SuccessfulEndPage
from psynet.prescreen import (
    AttentionTest,
    ColorBlindnessTest,
    ColorVocabularyTest,
    HugginsHeadphoneTest,
    LanguageVocabularyTest,
    LexTaleTest,
)
from psynet.timeline import Timeline


class Exp(psynet.experiment.Experiment):
    label = "Prescreens demo"

    timeline = Timeline(
        NoConsent(),
        # NOTE: Prescreens related to Tapping/REPP can be found in the 'repp_tests' demo, as is an
        # audio forced choice prescreen which is to be found the 'audio_forced_choice_test' demo.
        AttentionTest(),
        ColorBlindnessTest(),
        ColorVocabularyTest(),
        HugginsHeadphoneTest(),
        LanguageVocabularyTest(),
        LexTaleTest(),
        SuccessfulEndPage(),
    )
