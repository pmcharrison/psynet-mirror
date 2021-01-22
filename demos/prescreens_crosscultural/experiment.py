# pylint: disable=unused-import,abstract-method,unused-argument,no-member

##########################################################################################
#### Imports
##########################################################################################

import psynet.experiment

from psynet.timeline import join
from psynet.timeline import Timeline

from psynet.prescreen import LexTaleTest, LanguageVocabularyTest
from psynet.page import SuccessfulEndPage, InfoPage

##########################################################################################
#### Experiment
##########################################################################################



class Exp(psynet.experiment.Experiment):
    consent_audiovisual_recordings = False

    timeline = Timeline( 
    	LexTaleTest( # Prescreen1: Lextale test for English proficiency
    		performance_threshold=0), # this is set to 0 so everyone can pass the test, please increase for testing purposes
        InfoPage("You passed the english proficiency test! Congratulations.", time_estimate=3),
        LanguageVocabularyTest( # Prescreen2: Basic Language Vocabulary in target language
        	language = "Spanish_SP", #languages available: English_US, German, Hindi, Portuguese_BR, Spanish_SP
        	num_trials = 7, 
        	performance_threshold=6), 
        InfoPage("You passed the language vocabulary test! Congratulations.", time_estimate=3),
        SuccessfulEndPage()
    )

extra_routes = Exp().extra_routes()
