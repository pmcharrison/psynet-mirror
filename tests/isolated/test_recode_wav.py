import shutil
import tempfile

import pytest
from scipy.io import wavfile

from psynet.media import recode_wav
from psynet.utils import get_psynet_root


def test_recode_wav():
    input_file = get_psynet_root() / "tests/static/browser_audio_for_recoding.wav"

    with pytest.raises(ValueError, match="WAV header is invalid"):
        wavfile.read(input_file)

    with tempfile.NamedTemporaryFile(suffix=".wav") as temp_file:
        shutil.copyfile(input_file, temp_file.name)
        recode_wav(temp_file.name)
        wavfile.read(temp_file.name)
