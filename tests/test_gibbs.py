import pytest
from psynet.trial.gibbs import GibbsNode
from statistics import mean

from dallinger.models import Network

def make_gibbs_node(cls, experiment):
    seed = {
        "vector": [0, 1],
        "active_index": 0
    }
    return cls(
        seed=seed,
        degree=1,
        network=Network(),
        experiment=experiment,
        propagate_failure=False,
        participant=None
    )

@pytest.mark.usefixtures("demo_iterated_singing") # we can replace this with the gibbs demo eventually
def test_summarise(experiment_object):
    class Node1(GibbsNode):
        summarise_trials_method = "mean"
    n1 = make_gibbs_node(Node1, experiment_object)

    observations = [0, 1, 8, 9, 10]

    assert n1.summarise_trial_dimension(observations) == mean(observations)

    class Node2(GibbsNode):
        summarise_trials_method = "median"
    n2 = make_gibbs_node(Node2, experiment_object)

    assert n2.summarise_trial_dimension(observations) == 8

    class Node3(GibbsNode):
        summarise_trials_method = "kernel_mode"
        kernel_width = [1]
    n3 = make_gibbs_node(Node3, experiment_object)

    class Node4(GibbsNode):
        summarise_trials_method = "kernel_mode"
        kernel_width = [7]
    n4 = make_gibbs_node(Node4, experiment_object)

    assert n3.summarise_trial_dimension(observations) == 9.0
    assert 5.9 < n4.summarise_trial_dimension(observations) < 6.1

    observations_2 = [0, 1, 2, 3, 4, 5]
    assert 2.5 == n3.summarise_trial_dimension(observations_2)
    assert 2.5 == n4.summarise_trial_dimension(observations_2)

    class Node5a(GibbsNode):
        summarise_trials_method = "kernel_mode"
        kernel_width = "cv_ls"
    n5a = make_gibbs_node(Node5a, experiment_object)

    class Node5b(GibbsNode):
        summarise_trials_method = "kernel_mode"
        # kernel_width should be the same as Node4a, because cv_ls is the default
    n5b = make_gibbs_node(Node5b, experiment_object)

    observations_3 = [0, 2, 3]

    assert 1.5 < n5a.summarise_trial_dimension(observations_3) == n5b.summarise_trial_dimension(observations_3) < 2.0

    assert n5a.summarise_trial_dimension([0, 0, 0, 1]) == 0.0
    assert n5a.summarise_trial_dimension([0, 0, 0, 1, 3]) == 0.0
