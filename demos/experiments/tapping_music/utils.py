# imports
import json
from functools import cache
import numpy as np

from repp.config import sms_tapping
from repp.stimulus import REPPStimulus
from repp.utils import save_json_to_file, save_samples_to_file


class NumpySerializer(json.JSONEncoder):
    def default(self, obj):
        import numpy as np

        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.bool_):
            return super().encode(bool(obj))
        else:
            return super().default(obj)



# Generate Isochronous Stimulus With REPP
@cache
def create_iso_stim_with_repp(stim_name, stim_ioi):
    stimulus = REPPStimulus(stim_name, config=sms_tapping)
    stim_onsets = stimulus.make_onsets_from_ioi(stim_ioi)
    stim_prepared, stim_info, _ = stimulus.prepare_stim_from_onsets(stim_onsets)
    info = json.dumps(stim_info, cls=NumpySerializer)
    return stim_prepared, info


def generate_iso_stimulus_audio(path, stim_name, list_iois):
    stim_prepared, info = create_iso_stim_with_repp(stim_name, tuple(list_iois))
    save_samples_to_file(stim_prepared, path, sms_tapping.FS)


def generate_iso_stimulus_info(path, stim_name, list_iois):
    stim_prepared, info = create_iso_stim_with_repp(stim_name, tuple(list_iois))
    save_json_to_file(info, path)



# Music Stimulus Processing for Beat-Finding Tasks
def load_audio_only_from_file(fs, audio_filename):
    """
    Load audio file without requiring onsets file.

    Parameters
    ----------
    fs : int
        Target sampling frequency in Hz
    audio_filename : str
        Path to audio file

    Returns
    -------
    np.ndarray
        Loaded and resampled audio data
    """
    stimulus = REPPStimulus("temp", config=sms_tapping)
    return stimulus.load_resample_file(fs, audio_filename)


def filter_and_add_markers_no_onsets(stim, config):
    """
    Apply filtering and add markers without requiring onset information.

    Parameters
    ----------
    stim : np.ndarray
        Raw audio stimulus data
    config : Config
        Configuration parameters

    Returns
    -------
    tuple[np.ndarray, dict]
        - Prepared stimulus array
        - Dictionary containing stimulus information
    """
    stimulus = REPPStimulus("temp", config=config)

    # Apply spectral filtering
    filtered_stim = stimulus.filter_stim(
        config.FS, stim, config.STIM_RANGE, config.STIM_AMPLITUDE
    )

    # Create marker sounds
    markers_sound = stimulus.make_markers_sound(
        config.FS,
        config.MARKERS_DURATION,
        config.MARKERS_ATTACK,
        config.MARKERS_RANGE,
        config.MARKERS_AMPLITUDE
    )

    # Add markers at beginning and end
    markers_onsets, markers_channel = stimulus.add_markers_sound(
        config.FS,
        stim,
        config.MARKERS_IOI,
        config.MARKERS_BEGINNING,
        config.MARKERS_END,
        config.STIM_BEGINNING,
        config.MARKERS_END_SLACK
    )

    # Combine markers with filtered stimulus
    stim_prepared = stimulus.put_clicks_in_audio(markers_channel, config.FS, markers_sound, markers_onsets)
    stim_start_samples = int(round(config.STIM_BEGINNING * config.FS / 1000.0))
    stim_prepared[stim_start_samples:(stim_start_samples + len(filtered_stim))] += filtered_stim

    stim_duration = len(stim_prepared) / config.FS

    # Create minimal stim_info for beat-finding task
    stim_info = {
        'stim_duration': stim_duration,
        'stim_onsets': [],  # Empty for beat-finding
        'stim_shifted_onsets': [],  # Empty for beat-finding
        'onset_is_played': np.array([]),  # Empty for beat-finding
        'markers_onsets': markers_onsets,
        'stim_name': 'beat_finding_music'
    }

    return stim_prepared, stim_info


@cache
def create_music_stim_with_repp_beat_finding(stim_name, audio_filename, fs=44100):
    """
    Create music stimulus for beat-finding task without requiring onsets file.
    """
    # Load audio file
    stim = load_audio_only_from_file(fs, audio_filename)

    # Convert stereo to mono if needed
    if len(stim.shape) == 2:
        stim = stim[:, 0]

    # Apply filtering and add markers
    stim_prepared, stim_info = filter_and_add_markers_no_onsets(stim, sms_tapping)
    stim_info["stim_name"] = stim_name

    info = json.dumps(stim_info, cls=NumpySerializer)
    return stim_prepared, info


def generate_music_stimulus_audio(path, stim_name, audio_filename):
    stim_prepared, _ = create_music_stim_with_repp_beat_finding(stim_name, audio_filename)
    save_samples_to_file(stim_prepared, path, sms_tapping.FS)


def generate_music_stimulus_info(path, stim_name, audio_filename):
    stim_prepared, info = create_music_stim_with_repp_beat_finding(stim_name, audio_filename)
    save_json_to_file(info, path)
