import pytest

from psynet.asset import asset
from psynet.trial.static import StaticTrial


def test_trial_cue_rejects_asset_instances():
    with pytest.raises(
        ValueError,
        match="Trial.cue assets must be callables",
    ):
        StaticTrial.cue(
            definition={},
            assets={"stimulus": asset("http://example.com/file.wav")},
        )
