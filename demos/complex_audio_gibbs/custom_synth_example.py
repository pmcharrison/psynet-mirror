# This script generates an example file using the synth_stimulus function.
# It's not necessary for the experiment demo, but it's useful
# for checking the synthesis code independently of the main experiment.

from custom_synth import synth_stimulus

synth_stimulus([
    1.5,  # 1. Duration, percent
    0.1,  # 2. Tremolo rate, st
    0.05,  # 3. Tremolo depth, dB
    0,  # 4. Shift, semitones
    1,  # 5. Range, percent
    0,  # 6. Increase/Decrease, semitones
    0  # 7. Jitter, custom unit
], "example.wav", {
    'file': 'Harvard_L35_S01_0.wav'
})
