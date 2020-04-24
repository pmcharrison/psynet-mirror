from psynet.timeline import MediaSpec

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

    assert MediaSpec.merge(x, y, z).data == MediaSpec(audio={
        "stim-0": "stim-0.wav",
        "stim-1": "stim-1.wav",
        "stim-2": "stim-2b.wav"
    }).data
