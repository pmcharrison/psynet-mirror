
# This file contains the parameters to run singing experiments. 
# Different singing paradigms may need adjusted parameters.
# These parameters are based on Anglada-Tort et al. 2023 (please see methods section in the study): 
# Anglada-Tort, M., Harrison, P. M., Lee, H., & Jacoby, N. (2023). Large-scale iterated
#  singing experiments reveal oral transmission mechanisms underlying music evolution. 
# Current Biology, 33(8), 1472-1486.


# Global Parameters
note_duration = 0.5  # Duration of each note in seconds
note_silence = 0.3  # Silence duration between notes (in seconds)

# Roving reference tone parameters
# The roving mean determines the mean starting note (in MIDI) for melodies.
roving_mean_oldest = dict(default=57.5, male=51.5, female=63.5)
roving_mean_old = dict(default=55.5, male=49.5, female=61.5)
roving_mean = dict(default=55, low=49, high=61)

# Roving width specifies the range (in semitones) around the roving mean.
roving_width = dict(default=2.5)

# Maximum interval sizes for different reference modes
max_interval_size = dict(
    reference_is_first_note=9.5,
    reference_is_previous_note=4.5,
)

# Maximum overall pitch range for the melody
max_melody_pitch_range = dict(default=10)

# Duration of the silent gap between melodies in tasks like 2AFC
inter_stimulus_interval = 1.25

# Transposition parameters (in semitones)
transpose_within_trial_min_step_size = 0.0
transpose_within_trial_max_step_size = 2.5

# Slider parameters for user input
slider = dict(
    width=5,  # Range of the slider in semitones
    jitter=2,  # Random jitter added to the slider
    max_trial_bonus=0.05,  # Maximum bonus for accurate trials
    bonus_threshold_semitones=1,  # Threshold for bonus eligibility
)

# Singing imitation paradigm with 2-interval melodies
# This paradigm involves singing two intervals with specific constraints.
singing_2intervals = dict(
    sing_duration=4,  # Duration of the singing task (in seconds)
    max_abs_interval_error_treshold=5.5,  # Maximum allowed interval error
    max_melody_pitch_range=99,  # Maximum pitch range for the melody
    num_int=2,  # Number of intervals in the melody
    reference_mode="pitch_mode",  # Reference mode: "first_note", "previous_note", or "pitch_mode"
    max_pitch_height_seed=9.5,
    max_pitch_height=15,
    discrete=False,  # If True, quantizes to the 12-tone scale
    max_mean_interval_error=5.5,
    sample_rate=44100,  # Audio sample rate
    peak_time_difference=70,  # Time difference for peak detection (in ms)
    minimum_peak_height=0.05,  # Minimum height for pitch peaks
    db_threshold=-30,  # Threshold for pitch extraction
    db_end_threshold_realtive_2note_start=-15,  # End threshold relative to note start
    msec_silence=30,  # Minimum silence between segments (in ms)
    silence_beginning_ms=50,  # Silence at the beginning of the segment (in ms)
    extend_pitch_threshold_semitones=2.0,  # Threshold for pitch extension
    praat_extend_proximity_threshold_ms=150.0,  # Max allowed onset extension (in ms)
    cut_pre=40,  # Time ignored at the start of the segment (in ms)
    cut_post=50,  # Time ignored at the end of the segment (in ms)
    minimal_segment_duration=40,  # Minimum segment duration (in ms)
    pitch_range_allowed=[36, 75],  # Acceptable pitch range (in MIDI)
    singing_bandpass_range=[80, 6000],  # Bandpass filter range for audio (in Hz)
    singing_bandpass_range_praat_syllable=[40, 8000],  # Bandpass range for syllable extraction
    smoothing_env_window_ms=40,  # Smoothing window for envelope (in ms)
    compresssion_power=0.5,  # Non-linear compression power
    allowed_pitch_flactuations_witin_one_tone=8.0,  # Max pitch fluctuations within a tone (in semitones)
    percent_of_flcatuating_within_one_tone=35.0,  # Max percentage of fluctuation within a tone
    praat_octave_jump_cost=0.55,  # Cost for octave jumps in Praat
    praat_high_frequncy_favoring_octave_cost=0.03,  # High-frequency favoring cost in Praat
    praat_silence_threshold=0.03,  # Silence threshold in Praat
    end_melody=3.5,  # Time after melody ends (in seconds)
    end_singing=3.5,  # Time after singing ends (in seconds)
    end_recording=0.5,  # Time after recording ends (in seconds)
    upload=0.5,  # Time for uploading data (in seconds)
)

# Adjust max_interval_size based on reference mode
if singing_2intervals["reference_mode"] == "first_note":
    singing_2intervals["max_interval_size"] = max_interval_size["reference_is_first_note"]
elif singing_2intervals["reference_mode"] == "previous_note":
    singing_2intervals["max_interval_size"] = 6.5
elif singing_2intervals["reference_mode"] == "pitch_mode":
    singing_2intervals["max_interval_size"] = 6.5
