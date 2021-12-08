import pytest

from psynet.consent import NoConsent
from psynet.page import SuccessfulEndPage, ModularPage
from psynet.timeline import Timeline
from psynet.js_synth import Timbre, ADSRTimbre, JSSynth, Note


def test_if_chord_params_valid():
    with pytest.raises(
            ValueError, match="Sum of attack"
    ):
        test_timbre = Timbre(ADSRTimbre(attack=1, decay=1, sustain_amp=1, duration=0.5, release=1))
        test_note = Note(pitch=60,
                         timbre=test_timbre,
                         )

        example_js_synth = ModularPage(
            "js_synth",
            JSSynth(
                "Let's try creating a chord with invalid params.",
                test_note,
            ),
            time_estimate=5,
        )

        Timeline(
            NoConsent(),
            example_js_synth,
            SuccessfulEndPage(),
        )
