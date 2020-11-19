import pytest
from psynet.timeline import MediaSpec

def test_ids():
    media = MediaSpec(
        audio={
            'bier': '/static/audio/bier.wav',
            'batch': {
                'url': '/static/audio/file_concatenated.mp3',
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
