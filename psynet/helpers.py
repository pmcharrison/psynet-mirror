import os
import shutil

from .trial.non_adaptive import (
    StimulusSet,
    StimulusSpec,
    StimulusVersionSpec
)

class LocalAudioStimulusVersionSpec(StimulusVersionSpec):
    has_media = True
    media_ext = ".wav"

    @classmethod
    def generate_media(cls, definition, output_path):
        shutil.copyfile(definition["local_audio_path"], output_path)


def audio_stimulus_set_from_dir(input_dir: str, version: str, s3_bucket: str):
    stimuli = []
    participant_groups = [(f.name, f.path) for f in os.scandir(input_dir) if f.is_dir()]
    for participant_group, group_path in participant_groups:
        phases = [(f.name, f.path) for f in os.scandir(group_path) if f.is_dir()]
        for phase, phase_path in phases:
            blocks = [(f.name, f.path) for f in os.scandir(phase_path) if f.is_dir()]
            for block, block_path in blocks:
                audio_files = [(f.name, f.path) for f in os.scandir(block_path) if f.is_file() and f.path.endswith(".wav")]
                for audio_name, audio_path in audio_files:
                    stimuli.append(
                        StimulusSpec(
                            definition={
                                "name": audio_name,
                            },
                            phase=phase,
                            version_specs=[LocalAudioStimulusVersionSpec(
                                definition={
                                    "local_audio_path": audio_path
                                }
                            )],
                            participant_group=participant_group,
                            block=block
                        )
                    )
    return StimulusSet(stimuli, version=version, s3_bucket=s3_bucket)
