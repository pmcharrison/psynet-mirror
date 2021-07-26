# This script generates some example files using the synth_batch function.
# It's not necessary for the experiment demo, but it's useful
# for checking the synthesis code independently of the main experiment.
from custom_synth import synth_batch, TIMESTAMPS
import numpy as np

times = np.array(TIMESTAMPS)
effects = [{"name": "fade-out", "duration": 0.01}]
synth_batch(
    [
        np.column_stack((times, np.array([-300] * len(TIMESTAMPS)))),
        np.column_stack((times, np.array([-200] * len(TIMESTAMPS)))),
        np.column_stack((times, np.array([-100] * len(TIMESTAMPS)))),
        np.column_stack((times, np.array([0] * len(TIMESTAMPS)))),
        np.column_stack((times, np.array([100] * len(TIMESTAMPS)))),
        np.column_stack((times, np.array([200] * len(TIMESTAMPS)))),
        np.column_stack((times, np.array([300] * len(TIMESTAMPS)))),
    ],
    ['%dHz_change.wav' % ((i - 3) * 100) for i in range(7)],
    "synth_files/audio/norm_stim_vraiment_interro.wav",
    effects=effects,
)
