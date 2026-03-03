"""
Generate pre-rendered WAV stimuli for the single-chord emotion replication demo.

This script writes 28 files:
- 14 chord conditions
- each rendered with two timbres (piano, strings)
"""

from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np

SAMPLE_RATE = 22_050
DURATION_SEC = 4.0
MASTER_GAIN = 0.85

OUTPUT_DIR = Path("audio_file/stimuli")

CHORDS = {
    "major_root": [60, 64, 67],
    "major_first_inversion": [64, 67, 72],
    "major_second_inversion": [67, 72, 76],
    "minor_root": [60, 63, 67],
    "minor_first_inversion": [63, 67, 72],
    "minor_second_inversion": [67, 72, 75],
    "diminished_root": [60, 63, 66],
    "augmented_root": [60, 64, 68],
    "dominant_seventh_root": [60, 64, 67, 70],
    "dominant_seventh_third_inversion": [58, 60, 64, 67],
    "minor_seventh_root": [60, 63, 67, 70],
    "minor_seventh_third_inversion": [58, 60, 63, 67],
    "major_seventh_root": [60, 64, 67, 71],
    "major_seventh_third_inversion": [59, 60, 64, 67],
}

TIMBRES = ("piano", "strings")


def midi_to_hz(midi_note: int) -> float:
    return 440.0 * (2.0 ** ((midi_note - 69) / 12.0))


def adsr_envelope(
    n_samples: int,
    attack_sec: float,
    decay_sec: float,
    sustain_level: float,
    release_sec: float,
) -> np.ndarray:
    envelope = np.ones(n_samples, dtype=np.float64)
    attack_n = int(SAMPLE_RATE * attack_sec)
    decay_n = int(SAMPLE_RATE * decay_sec)
    release_n = int(SAMPLE_RATE * release_sec)

    if attack_n > 0:
        envelope[:attack_n] = np.linspace(0.0, 1.0, attack_n, endpoint=False)

    if decay_n > 0:
        decay_start = attack_n
        decay_end = min(attack_n + decay_n, n_samples)
        envelope[decay_start:decay_end] = np.linspace(
            1.0,
            sustain_level,
            max(decay_end - decay_start, 1),
            endpoint=False,
        )

    sustain_start = min(attack_n + decay_n, n_samples)
    sustain_end = max(n_samples - release_n, sustain_start)
    envelope[sustain_start:sustain_end] = sustain_level

    if release_n > 0:
        release_start = max(n_samples - release_n, 0)
        envelope[release_start:] = np.linspace(
            envelope[release_start],
            0.0,
            max(n_samples - release_start, 1),
            endpoint=True,
        )

    return envelope


def synthesize_note(frequency_hz: float, timbre: str, n_samples: int) -> np.ndarray:
    time_axis = np.arange(n_samples, dtype=np.float64) / SAMPLE_RATE
    signal = np.zeros(n_samples, dtype=np.float64)

    if timbre == "piano":
        harmonics = (
            (1, 1.00),
            (2, 0.58),
            (3, 0.36),
            (4, 0.22),
            (5, 0.14),
            (6, 0.08),
        )
        envelope = adsr_envelope(
            n_samples=n_samples,
            attack_sec=0.008,
            decay_sec=1.0,
            sustain_level=0.26,
            release_sec=0.9,
        )
    else:
        harmonics = (
            (1, 1.00),
            (2, 0.80),
            (3, 0.62),
            (4, 0.48),
            (5, 0.35),
            (6, 0.24),
            (7, 0.16),
        )
        envelope = adsr_envelope(
            n_samples=n_samples,
            attack_sec=0.22,
            decay_sec=0.5,
            sustain_level=0.84,
            release_sec=0.75,
        )

    for harmonic, amplitude in harmonics:
        base_phase = 2.0 * math.pi * frequency_hz * harmonic * time_axis
        if timbre == "strings":
            vibrato = 0.0035 * np.sin(2.0 * math.pi * 5.0 * time_axis)
            signal += amplitude * np.sin(base_phase + vibrato)
        else:
            signal += amplitude * np.sin(base_phase)

    return signal * envelope


def synthesize_chord(midi_notes: list[int], timbre: str) -> np.ndarray:
    n_samples = int(SAMPLE_RATE * DURATION_SEC)
    chord_signal = np.zeros(n_samples, dtype=np.float64)

    for midi_note in midi_notes:
        chord_signal += synthesize_note(
            midi_to_hz(midi_note), timbre=timbre, n_samples=n_samples
        )

    peak = np.max(np.abs(chord_signal))
    if peak > 0:
        chord_signal = (chord_signal / peak) * MASTER_GAIN

    return chord_signal


def write_wav(file_path: Path, signal: np.ndarray):
    pcm = np.int16(np.clip(signal, -1.0, 1.0) * 32_767)
    with wave.open(str(file_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(pcm.tobytes())


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    generated = 0
    for chord_id, midi_notes in CHORDS.items():
        for timbre in TIMBRES:
            signal = synthesize_chord(midi_notes, timbre=timbre)
            output_path = OUTPUT_DIR / f"{chord_id}_{timbre}.wav"
            write_wav(output_path, signal)
            generated += 1
            print(f"Generated: {output_path}")

    print(f"Done. Generated {generated} files in {OUTPUT_DIR}.")


if __name__ == "__main__":
    main()
