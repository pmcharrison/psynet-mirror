# Note: parselmouth must be installed with pip install praat-parselmouth
# The documentation of the audio methods can be found in the supplements of the paper "Gibbs Sampling with People",
# which can be obtained here:
# https://proceedings.neurips.cc/paper/2020/file/7880d7226e872b776d8b9f23975e2a3d-Supplemental.zip

import os
from parselmouth.praat import call, run_file
import numpy as np
from scipy import interpolate

# Helper methods
def update_pitch_points(pitch, manipulation, pitch_values, time):
    pitch_tier = call(manipulation, "Extract pitch tier")
    # Make sure the pitch Tier is empty
    call(pitch_tier, "Remove points between", min(pitch.xs()) - 0.001, max(pitch.xs()) + 0.001)
    for i in range(len(pitch_values)):
        call(pitch_tier, "Add point", time[i], pitch_values[i])
    call([manipulation, pitch_tier], "Replace pitch tier")
    return manipulation


def load_files(path):
    from parselmouth import Sound
    import json

    filename = os.path.basename(path)
    folder = path[:-len(filename)]

    # Use splitext() to get filename and extension separately.
    (file, ext) = os.path.splitext(filename)

    setting_path = folder + file + '.json'
    data = {
        "reference_tone": 210.8,
        "min_F0": 100,
        "max_F0": 500,
        "base_name": file,
        "step_size": 0.01
    }

    sound = Sound(path)
    data['duration'] = sound.xmax - sound.xmin
    pitch = call(sound, "To Pitch", data['step_size'], data['min_F0'], data['max_F0'])

    manipulation = call([sound, pitch], "To Manipulation")

    pitch_values = pitch.selected_array['frequency']

    # Remove NAs
    idxs = np.where(pitch_values == 0)
    pitch_values = np.delete(pitch_values, idxs)
    time = np.delete(pitch.xs(), idxs)

    pulses = call(pitch, "To PointProcess")

    return sound, manipulation, pitch, time, pitch_values, pulses, data


def cent2herz(ct, reference_tone):
    """Converts deviation in cents to a value in Herz"""
    st = ct / 100
    semi1 = np.log(np.power(2, 1 / 12))
    return np.exp(st * semi1) * reference_tone

def synth_stimulus(vector, output_path, chain_definition):
    """
    Synthesises a stimulus.

    Parameters
    ----------

    vector : list
        A vector of parameters as produced by the Gibbs sampler

    output_path : str
        The output path for the generated file.

    chain_definition
        The chain's definition object.
    """
    DIMENSION_NAMES = [
        'duration', 'tremolo_rate', 'tremolo_depth', 'pitch_shift', 'pitch_range', 'pitch_change', 'jitter'
    ]
    DIMENSIONS = len(DIMENSION_NAMES)

    assert isinstance(chain_definition, dict)
    assert len(vector) == DIMENSIONS

    parameters = dict(zip(DIMENSION_NAMES, vector))

    SYNTHESIS_FILES_DIR = 'synth_files/audio'

    filename = os.path.join(SYNTHESIS_FILES_DIR, chain_definition['file'])
    sound, manipulation, pitch, time, pitch_values, pulses, data = load_files(filename)
    if 'pitch_shift' in parameters and parameters['pitch_shift'] != 0:
        shift_st = int(parameters['pitch_shift'])
        pitch_values = pitch_shift(pitch_values, data['reference_tone'], shift_st)

    if 'pitch_range' in parameters and parameters['pitch_range'] != 1:
        scalar = float(parameters['pitch_range'])
        pitch_values = scale_pitch(pitch_values, scalar)

    if 'pitch_change' in parameters and parameters['pitch_change'] != 0:
        pitch_change = float(parameters['pitch_change'])
        pitch_change = cent2herz(pitch_change * 100, data['reference_tone']) - data['reference_tone']
        # Must be in ms
        duration_s = data['duration']
        duration_ms = duration_s * 1000
        points = np.stack((
            np.linspace(0, duration_ms, num=4),
            np.linspace(0, pitch_change * duration_s, num=4)
        ))
        pitch_values = inflection(
            time, pitch_values, points, 0, duration_ms
        )

    manipulation = update_pitch_points(pitch, manipulation, pitch_values, time)

    if 'jitter' in parameters and parameters['jitter'] != 0:
        jitter_amount = (int(parameters['jitter']))
        manipulation, pulses = jitter(manipulation, pulses, jitter_amount)

    if 'duration' in parameters and parameters['duration'] != 1:
        duration_scalar = (float(parameters['duration']))
        manipulation = scale_duration(manipulation, data['duration'], duration_scalar)

    sound = call(manipulation, "Get resynthesis (overlap-add)")

    if all([name in parameters and parameters[name] != 0 for name in ['tremolo_depth', 'tremolo_rate']]):
        tremolo_depth = (float(parameters['tremolo_depth']))
        tremolo_rate = (float(parameters['tremolo_rate']))
        intensity_tier = tremolo(data['duration'], tremolo_rate, tremolo_depth)
        sound = call([sound, intensity_tier], "Multiply", "yes")

    call(sound, "Save as WAV file", output_path)


# Synthesis methods
# Manipulation #1: Pitch level
def pitch_shift(pitch_values, reference_tone, shift_st):
    shift_hz = cent2herz(shift_st * 100, reference_tone) - reference_tone
    return pitch_values + shift_hz


# Manipulation #2: Pitch range
def scale_pitch(pitch_values, scalar):
    # Get the current pitch range
    full_range = pitch_values.max() - pitch_values.min()
    half_range = full_range / 2

    # Center all pitch values around 0
    pitch_rel = pitch_values - pitch_values.min() - half_range

    # Multiply with scalar and put it back to the original pitch height
    return (pitch_rel * scalar) + pitch_values.min() + half_range


# Manipulation #3: Pitch slope; adds a slope on top of existing pitch points
def inflection(time, pitch_values, points, start_time, duration_ms):
    # Convert all sound measures to seconds
    duration_s = duration_ms / 1000
    if not all([p >= 0 and p <= duration_ms for p in points[0]]):
        raise ValueError('Time must lay in specified duration')
    time_kernel = [start_time + p / 1000 for p in points[0]]

    # Convert cents to hertz
    pitch_kernel = [p for p in points[1]]

    idxs = [i for i, t in enumerate(time) if t >= start_time and t < start_time + duration_s]
    time = time[idxs]
    pitch_values = pitch_values[idxs]

    tck = interpolate.splrep(time_kernel, pitch_kernel, s=0)
    pitch_kernel_spline = interpolate.splev(time, tck, der=0)

    return pitch_values + pitch_kernel_spline


# Manipulation #4: F0 perturbation, aka jitter
def jitter(manipulation, pulses, jitter_amount):
    matrix = call(pulses, "To Matrix")
    r = jitter_amount / 100000

    formula = "self + randomGauss(0, %f)" % r
    call([matrix], "Formula", formula)

    pointprocess2 = call(matrix, "To PointProcess")
    call([pointprocess2, manipulation], "Replace pulses")
    return manipulation, pointprocess2


# Manipulation #5: Duration
def scale_duration(manipulation, duration, scalar):
    duration_tier = call("Create DurationTier", "tmp", 0, duration)
    call([duration_tier], "Add point", 0, scalar)
    call([duration_tier, manipulation], "Replace duration tier")
    return manipulation


# Manipulation #6 Periodic intensity variation, aka tremolo
def tremolo(duration, tremolo_rate, tremolo_depth):
    pulses = np.pi * (tremolo_rate * 2) / 100
    intensity_tier = call("Create IntensityTier", "tremolo", 0, duration)
    tim = round(duration * 100)
    ramp = 0

    for i in range(tim - 1):
        if i <= tim - 25 and ramp <= 1:
            ramp = ramp + 0.04
            if ramp > 1:
                ramp = 1
        else:
            ramp = ramp - 0.04
            if ramp < 0:
                ramp = 0
        intensity = 90 + (tremolo_depth / 2) * np.sin(pulses * i) * ramp
        call([intensity_tier], "Add point", i / 100, intensity)
    return intensity_tier



