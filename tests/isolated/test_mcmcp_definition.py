from types import SimpleNamespace

from psynet.trial.mcmcp import MCMCPTrial


def test_mcmcp_definition_includes_stimuli():
    dummy = SimpleNamespace(
        node=SimpleNamespace(
            definition={"current_state": {"x": 1}, "proposal": {"x": 2}}
        )
    )

    definition = MCMCPTrial.make_definition(dummy, experiment=None, participant=None)

    assert "first_stimulus" in definition
    assert "second_stimulus" in definition
    assert definition["first_stimulus"] == definition["ordered"][0]["value"]
    assert definition["second_stimulus"] == definition["ordered"][1]["value"]
