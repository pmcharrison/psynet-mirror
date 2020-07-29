import pytest
from psynet.timeline import MediaSpec
from psynet.utils import DuplicateKeyError

def test_merge_media_spec():
    x = MediaSpec(audio={
        "stim-0": "stim-0.wav"
    })
    y = MediaSpec(audio={
        "stim-1": "stim-1.wav",
        "stim-2": "stim-2.wav"
    })
    z = MediaSpec(audio={
        "stim-1": "stim-1.wav",
        "stim-2": "stim-2b.wav"
    })
    q = MediaSpec(audio={
        "stim-3": "stim-3.wav"
    })

    with pytest.raises(DuplicateKeyError) as e:
        MediaSpec.merge(x, y, z).data == MediaSpec(audio={
            "stim-0": "stim-0.wav",
            "stim-1": "stim-1.wav",
            "stim-2": "stim-2b.wav"
        })

    assert MediaSpec.merge(x, y).data == MediaSpec(audio={
            "stim-0": "stim-0.wav",
            "stim-1": "stim-1.wav",
            "stim-2": "stim-2.wav"
    }).data

    assert MediaSpec.merge(x, y, q).data == MediaSpec(audio={
            "stim-0": "stim-0.wav",
            "stim-1": "stim-1.wav",
            "stim-2": "stim-2.wav",
            "stim-3": "stim-3.wav"
    }).data
