from psynet.trial.non_adaptive import (
    stimulus_set_from_dir
)

version = "v1"

practice_stimuli = stimulus_set_from_dir(
    id_="practice_stimuli",
    input_dir="input/practice",
    media_ext=".wav",
    phase="practice",
    version=version,
    s3_bucket="audio-stimulus-set-from-dir-demo"
)
experiment_stimuli = stimulus_set_from_dir(
    id_="experiment_stimuli",
    input_dir="input/experiment",
    media_ext=".wav",
    phase="experiment",
    version=version,
    s3_bucket="audio-stimulus-set-from-dir-demo"
)

# Run ``python3 stimuli.py`` to prepare the stimulus set.
if __name__ == "__main__":
    for s in [practice_stimuli, experiment_stimuli]:
        s.prepare_media()
