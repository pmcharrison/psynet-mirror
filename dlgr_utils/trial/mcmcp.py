# pylint: disable=unused-argument,abstract-method

from .chain import ChainTrialGenerator, ChainTrial, ChainNode, ChainSource

class MCMCPTrial(ChainTrial):
    def make_definition(self, node, experiment, participant):
        order = ["current_state", "proposal"]
        random.shuffle(order)
        definition = node.definition.copy()
        definition["order"] = order
        return definition


class MCMCPTrialGenerator(ChainTrialGenerator):
    def create_node(self, trials, network, participant, experiment):
        return self.node_class(
            definition=self.summarise_answers(trials, participant, experiment),
            network=network,
            participant=participant
        )

    def finalise_trial(self, answer, trial, experiment, participant):
        # pylint: disable=unused-argument,no-self-use
        super().finalise_trial(answer, trial, experiment, participant)
        chosen_position = int(answer)
        trial.answer = {
            "chosen_position": chosen_position,
            "chosen_identity": trial.definition["order"][chosen_position]
        }

    def summarise_answers(self, trials, participant, experiment):
        if len(trials) == 1:
            return trials[0].answer
        raise NotImplementedError

class MCMCPNode(ChainNode):
    __mapper_args__ = {"polymorphic_identity": "mcmcp_node"}

    def __init__(self, network, participant, state=None, trials=None):
        if (state is not None) and (trials is not None):
            raise ValueError("Either <state> or <trials> must be None.")
        if state is None:
            state = self.get_new_state(trials, network, participant)
        proposal = self.get_proposal(state, network, participant)
        definition = {
            "current_state": state,
            "proposal": proposal
        }
        super().__init__(definition, network, participant)

    def get_proposal(self, state, network, partipant):
        raise NotImplementedError

# class MCMCPSource(ChainSource):
#     def generate_initial_state(self, network, experiment, participant):


class ImitationChainTrial(ChainTrial):
    __mapper_args__ = {"polymorphic_identity": "imitation_chain_trial"}

    def make_definition(self, node, experiment, participant):
        return node.definition
