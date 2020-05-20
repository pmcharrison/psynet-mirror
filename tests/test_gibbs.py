from psynet.trial.gibbs import GibbsNode

from statistics import mean

def test_summarise():
    class Node1(GibbsNode):
        summarise_trials_method = "mean"

    observations = [0, 1, 8, 9, 10]

    assert Node1.summarise_trial_dimension(observations) == mean(observations)

    class Node2(GibbsNode):
        summarise_trials_method = "median"

    assert Node2.summarise_trial_dimension(observations) == 8

    class Node3(GibbsNode):
        summarise_trials_method = "kernel_mode"
        kernel_width = [1]

    class Node4(GibbsNode):
        summarise_trials_method = "kernel_mode"
        kernel_width = [7]

    assert Node3.summarise_trial_dimension(observations) == 9.0
    assert 6 < Node4.summarise_trial_dimension(observations) < 7

    observations_2 = [0, 1, 2, 3, 4, 5]
    assert 2.5 == Node3.summarise_trial_dimension(observations_2)
    assert 2.5 == Node4.summarise_trial_dimension(observations_2)

    class Node5a(GibbsNode):
        summarise_trials_method = "kernel_mode"
        kernel_width = "cv_ls"

    class Node5b(GibbsNode):
        summarise_trials_method = "kernel_mode"
        # kernel_width should be the same as Node4a, because cv_ls is the default

    observations_3 = [0, 2, 3]

    assert 1.5 < Node5a.summarise_trial_dimension(observations_3) == Node5b.summarise_trial_dimension(observations_3) < 2.0

    import pdb; pdb.set_trace()
    assert Node5a.summarise_trial_dimension([0, 0, 0, 1]) == 0.0
    assert Node5a.summarise_trial_dimension([0, 0, 0, 1, 3]) == 0.0
