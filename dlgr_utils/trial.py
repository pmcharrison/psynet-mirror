from dallinger.models import Info

from .field import claim_field

from .timeline import (
    Page,
    InfoPage,
    CodeBlock,
    Module,
    join
)

class Trial(Info):
    answer = claim_field(1)

    def show(self, experiment, participant):
        """Should return a Page object that returns an answer that can be stored in Trial.answer."""
        raise NotImplementedError

class TrialGenerator(Module):
    # Generic trial generation module.
    #
    # Users will typically want to create a subclass of this class
    # that implements a custom prepare_trial function.
    # It typically won't be necessary to override finalise_trial,
    # but the option is there if you want it.

    def prepare_trial(self, experiment, participant):
        """Should return a Trial object."""
        raise NotImplementedError

    def finalise_trial(self, answer, trial, experiment, participant):
        """This can be optionally customised, for example to add some more postprocessing."""
        trial.answer = answer

    def _prepare_trial(self, experiment, participant):
        trial = self.prepare_trial(experiment=experiment, participant=participant)
        experiment.session.add(trial)
        participant.var.current_trial = trial.id
        experiment.save()

    def _show_trial(self, experiment, participant):
        trial = self._get_current_trial(self, participant)
        return trial.show(experiment=experiment, participant=participant)

    def _finalise_trial(self, experiment, participant):
        trial = self._get_current_trial(participant)
        answer = participant.answer
        self.finalise_trial(
            answer=answer,
            trial=trial,
            experiment=experiment,
            participant=participant
        )

    def _get_current_trial(self, participant):
        trial_id = participant.var.current_trial
        return self.trial_class.query.get(trial_id)

    elts = join(
        CodeBlock(self._prepare_trial),
        ReactivePage(self._show_trial),
        CodeBlock(self.finalise_trial)
    )

    def __init__(self, label, trial_class):
        self.label = label
        self.trial_class = trial_class

class NetworkTrialGenerator(TrialGenerator):
    #### The following method is overwritten from TrialGenerator
    def prepare_trial(self, experiment, participant):
        network = self.find_network(participant=participant, experiment=experiment)
        self.grow_network(network=network, participant=participant, experiment=experiment)
        node = self.find_node(network=network, participant=participant, experiment=experiment)
        self._create_trial(node=node, participant=participant, experiment=experiment)
    ####

    def find_network(self, participant, experiment):
        """Should find the appropriate network for the participant's next trial."""
        raise NotImplementedError

    def grow_network(self, network, participant, experiment):
        """Should extend the network if necessary by adding one or more nodes."""
        raise NotImplementedError

    def find_node(self, network, participant, experiment):
        """Should find the node to which the participant should be attached for the next trial."""
        raise NotImplementedError

    def create_trial(self, node, participant, experiment):
        """Should create and return a trial object for the participant at the current node."""
        raise NotImplementedError

    def _create_trial(self, node, participant, experiment):
        trial = self.create_trial(node=node, participant=participant, experiment=experiment)
        experiment.session.add(trial)
        experiment.save()
        return trial
        