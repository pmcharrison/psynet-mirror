from .chain import (
    ChainTrialGenerator,
    ChainNetwork,
    ChainNode,
    ChainTrial
)

class ImitationChainTrialGenerator(ChainTrialGenerator):
    def create_node(self, trials, network, participant, experiment):
        ChainNode(
            definition=self.summarise_answers(trials, participant, experiment),
            network=network
        )

    def summarise_answers(self, trials, participant, experiment):
        # pylint: disable=unused-argument
        if len(trials) == 1:
            return trials[0].answer
        raise NotImplementedError
    

class ImitationChainNetwork(ChainNetwork):
    def new_source(self, experiment, participant):
        raise NotImplementedError

# Need to implement open and close