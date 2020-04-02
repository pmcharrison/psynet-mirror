# pylint: disable=unused-argument,abstract-method

import random
from .chain import ChainTrialGenerator, ChainTrial, ChainNode, ChainSource

class MCMCPTrial(ChainTrial):
    __mapper_args__ = {"polymorphic_identity": "mcmcp_trial"}

    def show_trial(self, experiment, participant):
        """
        Should return a Page object that returns an answer that can be stored in Trial.answer.
        """
        raise NotImplementedError

    def make_definition(self, experiment, participant, **kwargs):
        node = kwargs["node"]
        order = ["current_state", "proposal"]
        random.shuffle(order)
        definition = node.definition.copy()
        definition["order"] = order
        return definition

class MCMCPNode(ChainNode):
    __mapper_args__ = {"polymorphic_identity": "mcmcp_node"}

    def get_proposal(self, state, experiment, participant):
        raise NotImplementedError

    def summarise_trials(self, trials, experiment, participant):
        """This function should summarise the answers to the provided trials."""
        chosen = [trial.definition[trial.answer["chosen_identity"]] for trial in trials]
        if len(chosen) == 1:
            return chosen[0]
        raise NotImplementedError

    def create_definition_from_seed(self, seed, experiment, participant):
        return {
            "current_state": seed,
            "proposal": self.get_proposal(seed, experiment, participant)
        }

class MCMCPSource(ChainSource):
    __mapper_args__ = {"polymorphic_identity": "mcmcp_source"}

    def generate_seed(self, network, experiment, participant):
        raise NotImplementedError

class MCMCPTrialGenerator(ChainTrialGenerator):
    def finalise_trial(self, answer, trial, experiment, participant):
        # pylint: disable=unused-argument,no-self-use
        super().finalise_trial(answer, trial, experiment, participant)
        chosen_position = int(answer)
        trial.answer = {
            "chosen_position": chosen_position,
            "chosen_identity": trial.definition["order"][chosen_position]
        }
