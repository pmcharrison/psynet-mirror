# This script generates some example files using the synth_batch function.
# It's not necessary for the experiment demo, but it's useful
# for checking the synthesis code independently of the main experiment.

import numpy as np
import os

from .custom_synth import synth_batch

BPFs = []
filenames = []
for idx, BPF_filepath in enumerate(os.listdir('synth_files/BPF')):
    BPFs.append(np.loadtxt('synth_files/BPF/' + BPF_filepath))
    filenames.append('synth_files/output/' + BPF_filepath.split('.')[0] + '.wav')

effects = [{
    'name': 'fade-out',
    'duration': 0.01
}]

synth_batch(
    BPFs,
    filenames,
    'synth_files/audio/3c_sp5_cr_su_i10_g00_bier_no-b_flat_235Hz_no-sil.wav',
    prepend_path='synth_files/audio/2b_sp5_cr_su_i10_g00_bier_b-only.wav',
    append_path='synth_files/audio/silence.wav',
    effects=effects
)
