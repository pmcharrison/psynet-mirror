from types import SimpleNamespace

from psynet.trial.gibbs import GibbsTrial


def test_gibbs_vectors_fall_back_to_definition():
    dummy = SimpleNamespace(
        _initial_vector=None,
        _updated_vector=None,
        definition={"vector": [1, 2, 3], "active_index": 1},
        answer=5,
        active_index=1,
    )

    initial_vector = GibbsTrial.initial_vector.__get__(dummy, GibbsTrial)
    updated_vector = GibbsTrial.updated_vector.__get__(dummy, GibbsTrial)

    assert initial_vector == [1, 2, 3]
    assert updated_vector == [1, 5, 3]
