from types import SimpleNamespace

from psynet.trial.gibbs import GibbsTrial


def test_gibbs_vectors_fall_back_to_definition():
    dummy = SimpleNamespace(
        _updated_vector=None,
        definition={"vector": [1, 2, 3], "initial_vector": [1, 2, 3]},
        answer=5,
        active_index=1,
    )

    initial_vector = GibbsTrial.initial_vector.__get__(dummy, GibbsTrial)
    dummy.initial_vector = initial_vector
    updated_vector = GibbsTrial.updated_vector.__get__(dummy, GibbsTrial)

    assert initial_vector == [1, 2, 3]
    assert updated_vector == [1, 5, 3]
