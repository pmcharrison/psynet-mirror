from psynet.modular_page import AudioPrompt, ModularPage, PushButtonControl
from psynet.prescreen import AudioForcedChoiceTest
from psynet.trial.static import StaticTrial

QUESTION = (
    "The user should read the sentence: '%s'. Please select the error category. The following errors can "
    "occur: (i) the wrong sentence is read, (ii) the sentence is read multiple times, and "
    "(iii) a part of the recording is cut out."
)


class ReadAudioTest(AudioForcedChoiceTest):
    def __init__(
        self,
        csv_path: str,
        answer_options: list,
        instructions: str,
        performance_threshold: int,
        question="",
        label="read_audio_test",
        n_stimuli_to_use: int = None,
        specific_indexes: list = None,
    ):
        super().__init__(
            csv_path=csv_path,
            answer_options=answer_options,
            instructions=instructions,
            question=question,
            performance_threshold=performance_threshold,
            label=label,
            n_stimuli_to_use=n_stimuli_to_use,
            specific_stimuli=specific_indexes,
        )

        # Each stimulus must have the field 'text'
        assert sum([1 for stimulus in self.stimuli if "text" in stimulus]) == len(
            self.stimuli
        )

    def trial(self, time_estimate: float):
        class AudioForcedChoiceTrial(StaticTrial):
            __mapper_args__ = {"polymorphic_identity": "read_audio_test_trial"}
            time_estimate = 5

            def show_trial(self, experiment, participant):
                return ModularPage(
                    "read_audio_test_trial",
                    AudioPrompt(
                        self.definition["url"],
                        QUESTION % self.definition["text"],
                    ),
                    PushButtonControl(self.definition["answer_options"]),
                    time_estimate=self.time_estimate,
                )

        return AudioForcedChoiceTrial
