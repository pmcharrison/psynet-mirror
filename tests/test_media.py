import pytest
import shutil
import tempfile
import parselmouth

from psynet.timeline import MediaSpec

from psynet.media import recode_wav

def test_ids():
    media = MediaSpec(
        audio={
            'bier': '/static/audio/bier.wav',
            'batch': {
                'url': '/static/audio/some_filename.mp3',
                'ids': ['funk_game_loop', 'honey_bee', 'there_it_is'],
                'type': 'batch'
            }
        },
        video={
            'vid1': 'my-video.mp4'
        }
    )
    assert media.ids == {
        'audio': {'bier', 'funk_game_loop', 'honey_bee', 'there_it_is'},
        'image': set(),
        'video': {'vid1'}
    }

def test_recode_wav():
    example = "tests/static/64_bit.wav"
    with tempfile.NamedTemporaryFile() as temp_file:
        shutil.copyfile(example, temp_file.name)
        recode_wav(temp_file.name)
        sound = parselmouth.Sound(temp_file.name)
        assert type(sound) == parselmouth.Sound
