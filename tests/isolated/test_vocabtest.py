from types import SimpleNamespace

from psynet.prescreen.vocabtest import VocabTrial


def test_vocab_finalize_definition_sets_hashes_after_asset_setup(monkeypatch):
    received_previous = []

    def choose_hashes(stimuli, previous):
        received_previous.extend(previous)
        return ["h"]

    def expire_then_return_assets(stimuli, hashes):
        trial.definition = {}
        return {"h": object()}

    maker = SimpleNamespace(
        choose_hashes=choose_hashes,
        get_assets=expire_then_return_assets,
    )
    trial = SimpleNamespace(
        trial_maker_id="vocab",
        assets={},
        definition={},
        node=SimpleNamespace(seed=[{"hash": "h"}]),
        trial_maker=maker,
    )

    monkeypatch.setattr(
        VocabTrial,
        "query",
        SimpleNamespace(
            filter_by=lambda **kwargs: SimpleNamespace(all=lambda: [trial])
        ),
    )

    definition = VocabTrial.finalize_definition(trial, {}, None, SimpleNamespace(id=1))

    assert received_previous == []
    assert definition["hashes"] == ["h"]
    assert "h" in trial.assets
