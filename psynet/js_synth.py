from .modular_page import Prompt
from .timeline import Event


class Chord(dict):
    def __init__(
        self,
        pitches,
        duration="default",
        silence="default",
        timbre="default",
    ):
        super().__init__(
            pitches=pitches,
            duration=duration,
            silence=silence,
            channel=timbre,
        )


class Note(Chord):
    def __init__(self, pitch, **kwargs):
        super().__init__(pitches=[pitch], **kwargs)


class Timbre(dict):
    """
    Timbre base class - not to be instantiated directly.
    """


class ADSRTimbre(Timbre):
    """
    ADSR timbre base class - not to be instantiated directly.
    """

    def __init__(
        self,
        attack=0.2,
        decay=0.1,
        sustain_amp=0.8,
        duration=1.0,
    ):
        super().__init__(
            attack=attack,
            decay=decay,
            sustain_amp=sustain_amp,
            duration=duration,
        )


class AdditiveTimbre(ADSRTimbre):
    def __init__(
        self,
        frequencies,
        amplitudes,
        **kwargs,
    ):
        super().__init__(**kwargs)
        assert len(frequencies) == len(amplitudes)

        self.frequencies = frequencies
        self.amplitudes = amplitudes
        self.num_harmonics = len(frequencies)

        self["type"] = "additive"
        self["freqs"] = frequencies
        self["amps"] = amplitudes


class HarmonicTimbre(ADSRTimbre):
    """
    Harmonic timbre

    Parameters
    ----------

    num_harmonics:
        Number of harmonics.

    rolloff:
        Roll-off in units of dB/octave
    """

    def __init__(
        self,
        num_harmonics=10,
        rolloff=12.0,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self.num_harmonics = num_harmonics
        self.roll_off = rolloff

        self["type"] = "harmonic"
        self["NH"] = num_harmonics
        self["rolloff"] = rolloff


class CompressedTimbre(ADSRTimbre):
    """
    Compressed harmonic timbre (inharmonicity coefficient of 1.9)

    Parameters
    ----------

    num_harmonics:
        Number of harmonics.

    rolloff:
        Roll-off in units of dB/octave
    """

    def __init__(
        self,
        num_harmonics=10,
        rolloff=12.0,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self.num_harmonics = num_harmonics
        self.rolloff = rolloff

        self["type"] = "compressed"
        self["NH"] = num_harmonics
        self["NH_max"] = 30
        self["rolloff"] = rolloff


class StretchedTimbre(ADSRTimbre):
    """
    Stretched harmonic timbre (inharmonicity coefficient of 2.1)

    Parameters
    ----------

    num_harmonics:
        Number of harmonics.

    rolloff:
        Roll-off in units of dB/octave
    """

    def __init__(
        self,
        num_harmonics=10,
        rolloff=12.0,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self.num_harmonics = num_harmonics
        self.rolloff = rolloff

        self["type"] = "stretched"
        self["NH"] = num_harmonics
        self["NH_max"] = num_harmonics
        self["rolloff"] = rolloff


class ShepardTimbre(ADSRTimbre):
    def __init__(
        self,
        num_octave_transpositions=4,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self.num_harmonics = 1
        self.num_octave_transpositions = num_octave_transpositions

        self["NSH"] = num_octave_transpositions


class InstrumentTimbre(Timbre):
    def __init__(self, type):
        super().__init__()
        assert type in [
            "piano",
            "xylophone",
            "violin",
            "guitar",
            "harpsichord",
            "saxophone",
            "clarinet",
            "flute",
            "trumpet",
        ]
        self["type"] = type
        self["NSH"] = 1  # <-- should not be necessary


class JSSynth(Prompt):
    """ "
    JS synthesizer.

    Parameters
    ----------

    text:
        Text to display to the participant. This can either be a string
        for plain text, or an HTML specification from ``flask.Markup``.

    sequence:
        Sequence to play to the participant. This should be a list of objects
        of class :class:`~psynet.js_synth.Chord` or of class :class:`~psynet.js_synth.Note`.

    timbre:
        Optional dictionary of timbres to draw from. The keys of this dictionary should link
        to the timbre arguments of the :class:`~psynet.js_synth.Chord`/:class:`~psynet.js_synth.Note` objects
        in ``sequence``. The values should be objects of class :class:`~psynet.js_synth.Timbre`.
        The default is a harmonic complex tone.

    default_duration:
        Default duration of each chord/note in seconds. This may be overridden by
        specifying the ``duration`` argument in the :class:`~psynet.js_synth.Chord`/:class:`~psynet.js_synth.Note` objects.

    default_silence:
        Default silence after each chord/note in seconds. This may be overridden by
        specifying the ``silence`` argument in the :class:`~psynet.js_synth.Chord`/:class:`~psynet.js_synth.Note` objects.

    text_align:
        CSS alignment of the text (default = ``"left"``).
    """

    def __init__(
        self,
        text,
        sequence,
        timbre="default",
        default_duration=0.75,
        default_silence=0.0,
        text_align="left",
    ):
        super().__init__(text=text, text_align=text_align)

        if timbre == "default":
            timbre = HarmonicTimbre()

        if isinstance(timbre, Timbre):
            timbre = dict(default=timbre)

        assert isinstance(timbre, dict)
        for t in timbre.values():
            assert isinstance(t, Timbre)

        assert isinstance(sequence, list)
        for elt in sequence:
            if not isinstance(elt, Chord):
                raise ValueError(
                    "Each element in 'sequence' must be an object of type 'Chord' or 'Note'."
                )

        options = dict(
            max_num_pitches=0,
            max_num_harmonics=10,  # <-- we should be able to decrease it to 0 but it fails with the piano
            max_num_octave_transpositions=4,
            instruments=[],
        )

        def consolidate_chord(chord):
            x = chord.copy()
            options["max_num_pitches"] = max(
                options["max_num_pitches"], len(x["pitches"])
            )

            if x["duration"] == "default":
                x["duration"] = default_duration
            if x["silence"] == "default":
                x["silence"] = default_silence
            if not x["channel"] in timbre:
                raise ValueError(
                    f"Selected timbre ({x['channel']}) was not found in timbre list ({timbre})."
                )

            return x

        sequence = [consolidate_chord(chord) for chord in sequence]

        channels = {key: {"synth": value} for key, value in timbre.items()}

        self.total_duration = 0.0
        for chord in sequence:
            self.total_duration += chord["duration"] + chord["silence"]

        for t in timbre.values():
            if hasattr(t, "num_harmonics"):
                options["max_num_harmonics"] = max(
                    options["max_num_harmonics"], t.num_harmonics
                )
            if hasattr(t, "num_octave_transpositions"):
                options["max_num_octave_transpositions"] = max(
                    options["max_num_octave_transpositions"],
                    t.num_octave_transpositions,
                )
            if isinstance(t, InstrumentTimbre):
                options["instruments"].append(t["type"])

        self.stimulus = dict(
            notes=sequence,
            channels=channels,
        )
        self.options = options

    macro = "js_synth"

    @property
    def metadata(self):
        return {"stimulus": self.stimulus, "options": self.options}

    def update_events(self, events):
        super().update_events(events)

        events["promptStart"] = Event(is_triggered_by="trialStart")
        events["promptEnd"] = Event(
            is_triggered_by="trialStart", delay=self.total_duration
        )  #
        events["trialFinish"].add_trigger("promptEnd")
