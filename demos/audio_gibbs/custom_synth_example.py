# This script generates an example file using the synth_stimulus function.
# It's not necessary for the experiment demo, but it's useful
# for checking the synthesis code independently of the main experiment.

from .custom_synth import synth_stimulus

synth_stimulus([-300, -200, -100, 100, 200], "synth_files/output_single/example.wav")
