import pytest
from psynet.trial.mcmcp import MCMCPNode
from statistics import mean

from dallinger.models import Network

def make_mcmcp_node(cls, experiment):
    seed = {
        "age": 55
    }
    return cls(
        seed=seed,
        degree=1,
        network=Network(),
        experiment=experiment,
        propagate_failure=False,
        participant=None
    )

def make_mcmcp_trial(cls, experiment, node, participant, answer):
    t = cls(
        experiment,
        node,
        participant=participant,
        propagate_failure=False,
        is_repeat_trial=False
    )
    t.answer = answer
    return t

def summarise_trials(trial_class, experiment_object, node, participant, answers):
    trials = [
        make_mcmcp_trial(
            trial_class,
            experiment_object,
            node,
            participant=participant,
            answer=answer
        )
        for answer in answers
    ]
    return node.summarise_trials(trials, experiment_object, participant)

@pytest.mark.usefixtures("demo_mcmcp") # we can replace this with the MCMCP demo eventually
def test_summarise(experiment_module, experiment_object, participant):
    node = make_mcmcp_node(experiment_module.CustomNode, experiment_object)

    trial_class = experiment_module.CustomTrial

    assert summarise_trials(
        trial_class, experiment_object, node, participant,
        answers=[{"role": "proposal"}]
    ) == node.definition["proposal"]

    assert summarise_trials(
        trial_class, experiment_object, node, participant,
        answers=[{"role": "current_state"}]
    ) == node.definition["current_state"]

    assert summarise_trials(
        trial_class, experiment_object, node, participant,
        answers=[{"role": "proposal"}, {"role": "proposal"}, {"role": "current_state"}]
    ) == node.definition["proposal"]

    assert summarise_trials(
        trial_class, experiment_object, node, participant,
        answers=[{"role": "proposal"}, {"role": "current_state"}, {"role": "current_state"}]
    ) == node.definition["current_state"]

    assert summarise_trials(
        trial_class, experiment_object, node, participant,
        answers=[{"role": "proposal"}, {"role": "current_state"}]
    ) in [
        node.definition["current_state"],
        node.definition["proposal"]
    ]
