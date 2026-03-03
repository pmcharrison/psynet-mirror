"""
Generate pre-rendered WAV stimuli for the single-chord emotion replication demo.

This script uses FluidSynth with the system GM SoundFont to render sampled
instrument timbres:
- piano: Acoustic Grand Piano (program 0)
- strings: String Ensemble 1 (program 48)
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np

SAMPLE_RATE = 22_050
DURATION_SEC = 4.0
MASTER_GAIN = 0.85
TICKS_PER_QUARTER = 480
TEMPO_MICROSECONDS_PER_QUARTER = 500_000  # 120 BPM

OUTPUT_DIR = Path("audio_file/stimuli")
SOUNDFONT_PATH = Path("/usr/share/sounds/sf2/default-GM.sf2")

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

PROGRAM_BY_TIMBRE = {"piano": 0, "strings": 48}


def encode_vlq(value: int) -> bytes:
    if value == 0:
        return b"\x00"
    chunks = [value & 0x7F]
    value >>= 7
    while value:
        chunks.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(chunks))


def build_midi_bytes(notes: list[int], program: int) -> bytes:
    duration_ticks = int((DURATION_SEC / 0.5) * TICKS_PER_QUARTER)
    events = [
        encode_vlq(0)
        + b"\xff\x51\x03"
        + TEMPO_MICROSECONDS_PER_QUARTER.to_bytes(3, "big"),
        encode_vlq(0) + bytes([0xC0, program]),
    ]

    for note in notes:
        events.append(encode_vlq(0) + bytes([0x90, note, 100]))

    first = True
    for note in notes:
        delta = duration_ticks if first else 0
        events.append(encode_vlq(delta) + bytes([0x80, note, 64]))
        first = False

    events.append(encode_vlq(0) + b"\xff\x2f\x00")
    track_data = b"".join(events)
    track_chunk = b"MTrk" + len(track_data).to_bytes(4, "big") + track_data
    header_chunk = (
        b"MThd"
        + (6).to_bytes(4, "big")
        + (0).to_bytes(2, "big")
        + (1).to_bytes(2, "big")
        + TICKS_PER_QUARTER.to_bytes(2, "big")
    )
    return header_chunk + track_chunk


def render_with_fluidsynth(midi_path: Path, output_path: Path):
    command = [
        "fluidsynth",
        "-ni",
        str(SOUNDFONT_PATH),
        str(midi_path),
        "-F",
        str(output_path),
        "-r",
        str(SAMPLE_RATE),
        "-o",
        "synth.reverb.active=0",
        "-o",
        "synth.chorus.active=0",
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)


def load_and_process_wave(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as wav_file:
        n_channels = wav_file.getnchannels()
        sample_rate = wav_file.getframerate()
        sample_width = wav_file.getsampwidth()
        frames = wav_file.readframes(wav_file.getnframes())

    if sample_rate != SAMPLE_RATE:
        raise ValueError(f"Unexpected sample rate {sample_rate} in {path}")
    if sample_width != 2:
        raise ValueError(f"Expected 16-bit audio in {path}")

    samples = np.frombuffer(frames, dtype=np.int16).reshape(-1, n_channels)
    mono = samples.mean(axis=1).astype(np.float64) / 32767.0

    target_samples = int(SAMPLE_RATE * DURATION_SEC)
    if len(mono) < target_samples:
        mono = np.pad(mono, (0, target_samples - len(mono)))
    else:
        mono = mono[:target_samples]

    peak = np.max(np.abs(mono))
    if peak > 0:
        mono = (mono / peak) * MASTER_GAIN
    return mono


def write_wave(path: Path, signal: np.ndarray):
    pcm = np.int16(np.clip(signal, -1.0, 1.0) * 32767)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(pcm.tobytes())


def ensure_dependencies():
    if shutil.which("fluidsynth") is None:
        raise RuntimeError(
            "fluidsynth binary not found. Install with: sudo apt-get install fluidsynth"
        )
    if not SOUNDFONT_PATH.exists():
        raise RuntimeError(
            f"SoundFont not found at {SOUNDFONT_PATH}. "
            "Install with: sudo apt-get install fluid-soundfont-gm"
        )


def render_chord(chord_notes: list[int], timbre: str, output_path: Path):
    with tempfile.TemporaryDirectory() as tmp_dir:
        midi_path = Path(tmp_dir) / "chord.mid"
        raw_wav_path = Path(tmp_dir) / "raw.wav"

        midi_path.write_bytes(
            build_midi_bytes(
                notes=chord_notes,
                program=PROGRAM_BY_TIMBRE[timbre],
            )
        )
        render_with_fluidsynth(midi_path=midi_path, output_path=raw_wav_path)
        processed = load_and_process_wave(raw_wav_path)
        write_wave(output_path, processed)


def main():
    ensure_dependencies()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    generated = 0
    for chord_id, midi_notes in CHORDS.items():
        for timbre in PROGRAM_BY_TIMBRE:
            output_path = OUTPUT_DIR / f"{chord_id}_{timbre}.wav"
            render_chord(midi_notes, timbre, output_path)
            generated += 1
            print(f"Generated: {output_path}")

    print(f"Done. Generated {generated} files in {OUTPUT_DIR}.")


if __name__ == "__main__":
    main()
