"""
Close-replication demo of Lahdelma & Eerola (2016):
"Single chords convey distinct emotional qualities to both naive and expert listeners".

DOI: 10.1177/0305735614552006
"""

from pathlib import Path

from markupsafe import Markup

import psynet.experiment
from psynet.asset import asset  # noqa
from psynet.bot import Bot
from psynet.demography.general import Age, CountryOfBirth, FormalEducation, Gender
from psynet.demography.gmsi import GMSI
from psynet.modular_page import (
    AudioPrompt,
    ModularPage,
    MultiRatingControl,
    RatingScale,
)
from psynet.page import InfoPage, VolumeCalibration
from psynet.timeline import Event, Timeline
from psynet.trial.static import StaticNode, StaticTrial, StaticTrialMaker

STIMULUS_DIR = Path("audio_file/stimuli")
TIMBRES = ("piano", "strings")

CHORD_CONDITIONS = (
    {
        "stimulus_id": "major_root",
        "chord_label": "C major triad",
        "chord_type": "major_triad",
        "inversion": "root",
    },
    {
        "stimulus_id": "major_first_inversion",
        "chord_label": "C major triad",
        "chord_type": "major_triad",
        "inversion": "first",
    },
    {
        "stimulus_id": "major_second_inversion",
        "chord_label": "C major triad",
        "chord_type": "major_triad",
        "inversion": "second",
    },
    {
        "stimulus_id": "minor_root",
        "chord_label": "C minor triad",
        "chord_type": "minor_triad",
        "inversion": "root",
    },
    {
        "stimulus_id": "minor_first_inversion",
        "chord_label": "C minor triad",
        "chord_type": "minor_triad",
        "inversion": "first",
    },
    {
        "stimulus_id": "minor_second_inversion",
        "chord_label": "C minor triad",
        "chord_type": "minor_triad",
        "inversion": "second",
    },
    {
        "stimulus_id": "diminished_root",
        "chord_label": "C diminished triad",
        "chord_type": "diminished_triad",
        "inversion": "root",
    },
    {
        "stimulus_id": "augmented_root",
        "chord_label": "C augmented triad",
        "chord_type": "augmented_triad",
        "inversion": "root",
    },
    {
        "stimulus_id": "dominant_seventh_root",
        "chord_label": "C dominant seventh",
        "chord_type": "dominant_seventh",
        "inversion": "root",
    },
    {
        "stimulus_id": "dominant_seventh_third_inversion",
        "chord_label": "C dominant seventh",
        "chord_type": "dominant_seventh",
        "inversion": "third",
    },
    {
        "stimulus_id": "minor_seventh_root",
        "chord_label": "C minor seventh",
        "chord_type": "minor_seventh",
        "inversion": "root",
    },
    {
        "stimulus_id": "minor_seventh_third_inversion",
        "chord_label": "C minor seventh",
        "chord_type": "minor_seventh",
        "inversion": "third",
    },
    {
        "stimulus_id": "major_seventh_root",
        "chord_label": "C major seventh",
        "chord_type": "major_seventh",
        "inversion": "root",
    },
    {
        "stimulus_id": "major_seventh_third_inversion",
        "chord_label": "C major seventh",
        "chord_type": "major_seventh",
        "inversion": "third",
    },
)

PANAS_POSITIVE_ITEMS = (
    "interested",
    "excited",
    "strong",
    "enthusiastic",
    "proud",
)

PANAS_NEGATIVE_ITEMS = (
    "distressed",
    "upset",
    "guilty",
    "scared",
    "hostile",
)


def get_nodes():
    nodes = []
    for condition in CHORD_CONDITIONS:
        for timbre in TIMBRES:
            stimulus_filename = f"{condition['stimulus_id']}_{timbre}.wav"
            stimulus_path = STIMULUS_DIR / stimulus_filename
            nodes.append(
                StaticNode(
                    definition={
                        **condition,
                        "timbre": timbre,
                        "stimulus_filename": stimulus_filename,
                    },
                    assets={
                        "stimulus_audio": asset(
                            stimulus_path,
                            extension=".wav",
                            cache=True,
                        ),
                    },
                )
            )
    return nodes


def panas_page():
    return ModularPage(
        "panas",
        Markup(
            """
            <p>
                Please indicate to what extent you feel each adjective right now.
            </p>
            <p>
                Scale: 1 = very slightly or not at all; 5 = extremely.
            </p>
            """
        ),
        MultiRatingControl(
            *[
                RatingScale(
                    name=f"panas_{item}",
                    values=5,
                    title=item.capitalize(),
                    min_description="Very slightly or not at all",
                    max_description="Extremely",
                )
                for item in PANAS_POSITIVE_ITEMS + PANAS_NEGATIVE_ITEMS
            ]
        ),
        time_estimate=45,
        save_answer="panas",
    )


def chord_rating_scales():
    return [
        RatingScale(
            name="valence",
            values=5,
            title="Valence",
            description="Is the chord conveying positive or negative feelings?",
            min_description="Negative",
            max_description="Positive",
        ),
        RatingScale(
            name="tension",
            values=5,
            title="Tension",
            description="How tense is the chord? Is it relaxed or tense and agitated?",
            min_description="Relaxed",
            max_description="Tense",
        ),
        RatingScale(
            name="energy",
            values=5,
            title="Energy",
            description="Does the chord sound weak and feeble, or strong and energetic?",
            min_description="Low",
            max_description="High",
        ),
        RatingScale(
            name="nostalgia_longing",
            values=5,
            title="Nostalgia / longing",
            description="Is the chord conveying nostalgia, wistfulness, or longing?",
            min_description="Very slightly or not at all",
            max_description="Extremely",
        ),
        RatingScale(
            name="melancholy_sadness",
            values=5,
            title="Melancholy / sadness",
            description="How much melancholy or sadness does the chord express?",
            min_description="Very slightly or not at all",
            max_description="Extremely",
        ),
        RatingScale(
            name="interest_expectancy",
            values=5,
            title="Interest / expectancy",
            description=(
                "Is the chord sounding resolutive and definitive, "
                "or conveying interest and expectancy?"
            ),
            min_description="Very slightly or not at all",
            max_description="Extremely",
        ),
        RatingScale(
            name="happiness_joy",
            values=5,
            title="Happiness / joy",
            description="How much happiness or joy does the chord express?",
            min_description="Very slightly or not at all",
            max_description="Extremely",
        ),
        RatingScale(
            name="tenderness",
            values=5,
            title="Tenderness",
            description="Is the chord sounding tender and affectionate?",
            min_description="Very slightly or not at all",
            max_description="Extremely",
        ),
        RatingScale(
            name="liking_preference",
            values=5,
            title="Liking / preference",
            description=(
                "How much did you like the chord? "
                "This is a purely subjective rating."
            ),
            min_description="Very slightly or not at all",
            max_description="Extremely",
        ),
    ]


class ChordEmotionTrial(StaticTrial):
    time_estimate = 25

    def show_trial(self, experiment, participant):
        return ModularPage(
            "chord_evaluation",
            AudioPrompt(
                self.assets["stimulus_audio"],
                (
                    "Listen to the chord as many times as you like. "
                    "Then rate the emotional qualities it seems to convey."
                ),
                controls={"Play from start": "Replay"},
            ),
            MultiRatingControl(*chord_rating_scales()),
            events={"submitEnable": Event(is_triggered_by="promptEnd")},
            time_estimate=self.time_estimate,
        )


class Exp(psynet.experiment.Experiment):
    label = "Single-chord emotion replication"
    test_num_bots = 1

    timeline = Timeline(
        VolumeCalibration(),
        InfoPage(
            Markup(
                """
                <p>
                    In this experiment you will evaluate single isolated chords.
                </p>
                <p>
                    You will hear 28 total stimuli:
                    14 chord conditions, each presented with piano and strings timbres.
                </p>
                <p>
                    You can replay each chord as many times as you like before rating it.
                </p>
                """
            ),
            time_estimate=10,
        ),
        InfoPage(
            Markup(
                """
                <p>
                    Please treat each chord as an independent sound event.
                </p>
                <p>
                    The first three scales are bipolar (valence, tension, energy),
                    while the remaining six use intensity ratings.
                </p>
                <p>
                    Try to rely on your immediate impression of each chord.
                </p>
                """
            ),
            time_estimate=10,
        ),
        Age(),
        Gender(),
        CountryOfBirth(label="nationality"),
        FormalEducation(),
        panas_page(),
        GMSI(
            short_version=True,
            subscales=[
                "Musical Training",
                "Perceptual Abilities",
                "Singing Abilities",
                "Instrument",
            ],
        ),
        StaticTrialMaker(
            id_="single_chord_emotion_ratings",
            trial_class=ChordEmotionTrial,
            nodes=get_nodes,
            expected_trials_per_participant="n_nodes",
            max_trials_per_participant="n_nodes",
            allow_repeated_nodes=False,
            balance_across_nodes=False,
        ),
        InfoPage(
            "Thank you for participating!",
            time_estimate=3,
        ),
    )

    def test_check_bot(self, bot: Bot, **kwargs):
        assert len(bot.alive_trials) == len(get_nodes())
