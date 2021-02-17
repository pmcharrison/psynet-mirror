# pylint: disable=unused-import,abstract-method,unused-argument,no-member

##########################################################################################
#### Imports
##########################################################################################

import psynet.experiment
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.prescreen import LanguageVocabularyTest, LexTaleTest
from psynet.timeline import Timeline

##########################################################################################
#### Experiment
##########################################################################################


class Exp(psynet.experiment.Experiment):
    consent_audiovisual_recordings = False

    timeline = Timeline(
        LexTaleTest(  # Prescreen1: Lextale test for English proficiency
            num_trials=7, performance_threshold=0
        ),  # this is set to 0 so everyone can pass the test, please increase for testing purposes
        InfoPage(
            "You passed the English proficiency test! Congratulations.", time_estimate=3
        ),
        LanguageVocabularyTest(  # Prescreen2: Basic Language Vocabulary: select target language
            language_code="es-ES",  # languages available: en-US, es-ES, de-DE, in-HI, pt-BR
            num_trials=7,
            performance_threshold=4,
        ),  # the particiapnt needs 5 correct answers to pass
        InfoPage(
            "You passed the language vocabulary test! Congratulations.", time_estimate=3
        ),
        SuccessfulEndPage(),
    )


extra_routes = Exp().extra_routes()
