# This script generates an example file using the synth_stimulus function.
# It's not necessary for the experiment demo, but it's useful
# for checking the synthesis code independently of the main experiment.

from custom_synth import synth_stimulus

synth_stimulus([0, 0, 112, 0, 152, 112, 0.5, 0.2], "test.mp4", {})
