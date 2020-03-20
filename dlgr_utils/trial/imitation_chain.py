# pylint: disable=unused-argument,abstract-method

from .chain import ChainTrial, ChainNode, ChainSource, ChainTrialGenerator

class ImitationChainTrial(ChainTrial):
    __mapper_args__ = {"polymorphic_identity": "imitation_chain_trial"}

    def make_definition(self, node, experiment, participant):
        """Each trial is a faithful reproduction of the latest node in the chain."""
        return node.definition
        
class ImitationChainNode(ChainNode):
    def create_definition_from_seed(self, seed, experiment, participant):
        """The next node in the chain is a faithful reproduction of the previous iteration."""
        return seed

    def summarise_trials(self, trials, experiment, participant):
        """This function should summarise the answers to the provided trials."""
        if len(trials) == 1:
            return trials[0].answer
        raise NotImplementedError

class ImitationChainSource(ChainSource):
    def generate_seed(self, network, experiment, participant):
        raise NotImplementedError

class ImitationChainTrialGenerator(ChainTrialGenerator):
    pass