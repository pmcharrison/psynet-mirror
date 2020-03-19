# pylint: disable=unused-argument,abstract-method

from .chain import ChainTrialGenerator, ChainTrial

class ImitationChainTrialGenerator(ChainTrialGenerator):
    def create_node(self, trials, network, participant, experiment):
        return self.node_class(
            definition=self.summarise_answers(trials, participant, experiment),
            network=network
        )

    def summarise_answers(self, trials, participant, experiment):
        if len(trials) == 1:
            return trials[0].answer
        raise NotImplementedError

class ImitationChainTrial(ChainTrial):
    __mapper_args__ = {"polymorphic_identity": "imitation_chain_trial"}

    def derive_definition(self, node, experiment, participant):
        return node.definition
