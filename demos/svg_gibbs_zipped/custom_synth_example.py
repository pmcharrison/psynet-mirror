# This script generates an example file using the synth_batch function.
# It's not necessary for the experiment demo, but it's useful
# for checking the synthesis code independently of the main experiment.

from custom_synth_batch import synth_batch

synth_batch([[0, 0, 10], [0, 0, 50], [0, 0, 90]], "test.batch", {})
