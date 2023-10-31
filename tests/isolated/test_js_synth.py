# The problem:
# A recent version of JSSynth introduced a MIDI-like representation where
# chord events (i.e. events containing multiple sounding pitches) were broken down
# multiple simultaneous note events (i.e. events containing single pitches).
# This latter representation worked well for InstrumentTimbres (and enabled support for mixed timbres within chords)
# but it failed for ADSRTimbres because the underlying implementation needs to know how many notes are
# sounding simultaneously.
#
# The solution:
# When compiling the JSSynth instructions, check whether the timbre is ADSRTimbre.
# If so, do NOT break it down into individual notes.
# If mixed timbres/pans are detected, throw an error as these aren't supported by ADSRTimbres yet.

import pytest

from psynet.js_synth import ADSRTimbre, Chord, InstrumentTimbre, JSSynth


def test_pan_mixing_adsr():
    with pytest.raises(
        ValueError,
        match="Mixing multiple timbres within chords is not supported for ADSRTimbres",
    ):
        JSSynth(
            text="",
            sequence=[Chord([60, 64], timbre=["t1", "t2"])],
            timbre={
                "t1": ADSRTimbre(release=1),
                "t2": ADSRTimbre(release=2),
            },
        )


def test_chord_representations_adsr():
    prompt = JSSynth(
        text="",
        sequence=[Chord([60, 64, 67])],
        timbre=ADSRTimbre(),
    )
    assert prompt.stimulus == {
        "notes": [
            {
                "pitches": [60, 64, 67],
                "duration": 0.75,
                "silence": 0.0,
                "channel": "default",
                "pan": [0.0, 0.0, 0.0],
                "volume": 1.0,
                "onset": 0,
            }
        ],
        "channels": {
            "default": {
                "synth": {
                    "attack": 0.2,
                    "decay": 0.1,
                    "sustain_amp": 0.8,
                    "release": 0.4,
                }
            }
        },
    }


def test_chord_representations_instrument():
    prompt = JSSynth(
        text="",
        sequence=[Chord([60, 64, 67], timbre=["a", "b", "a"])],
        timbre={
            "a": InstrumentTimbre("flute"),
            "b": InstrumentTimbre("guitar"),
        },
    )
    assert prompt.stimulus == {
        "notes": [
            {
                "pitches": [60],
                "duration": 0.75,
                "silence": 0.0,
                "channel": "a",
                "pan": [0.0],
                "volume": 1.0,
                "onset": 0,
            },
            {
                "pitches": [64],
                "duration": 0.75,
                "silence": 0.0,
                "channel": "b",
                "pan": [0.0],
                "volume": 1.0,
                "onset": 0,
            },
            {
                "pitches": [67],
                "duration": 0.75,
                "silence": 0.0,
                "channel": "a",
                "pan": [0.0],
                "volume": 1.0,
                "onset": 0,
            },
        ],
        "channels": {
            "a": {
                "synth": {
                    "type": "flute",
                    "samples": None,
                    "base_url": "",
                    "num_octave_transpositions": 0,
                }
            },
            "b": {
                "synth": {
                    "type": "guitar",
                    "samples": None,
                    "base_url": "",
                    "num_octave_transpositions": 0,
                }
            },
        },
    }
