from sqlalchemy import Column, Float, Integer

from psynet.trial import ChainNode, ChainTrial
from psynet.trial.chain import ChainTrialMaker


class StaircaseNode(ChainNode):
    # k up 2 down procedure
    k = 2

    n_consecutive_correct = Column(Integer)
    parameter = Column(Float)

    def __init__(self, *args, parameter=None, **kwargs):
        self.parameter = parameter
        super().__init__(*args, **kwargs)

    def init_next_node(self, next_node: ChainNode):
        assert self.network.chain_type == "within"

        if self.degree == 0:
            self.n_consecutive_correct = 0

        next_node.parameter = self.parameter
        next_node.n_consecutive_correct = self.n_consecutive_correct

        if self.trial.score == 1:
            next_node.n_consecutive_correct += 1

            if next_node.n_consecutive_correct == self.k:
                next_node.increase_difficulty()
                next_node.n_consecutive_correct = 0

        elif self.trial.score == 0:
            next_node.decrease_difficulty()
            next_node.n_consecutive_correct = 0

        else:
            raise ValueError(f"Unexpected score: {self.trial.score}")

    @property
    def definition(self):
        return {"parameter": self.parameter}

    def increase_difficulty(self):
        raise NotImplementedError()

    def decrease_difficulty(self):
        raise NotImplementedError()

    def create_seed(self, experiment, participant):
        return {}


class StaircaseTrial(ChainTrial):
    parameter = Column(Float)

    def __init__(self, *args, **kwargs):
        self.parameter = kwargs["node"].parameter
        super().__init__(*args, **kwargs)

    def make_definition(self, experiment, participant):
        return {"parameter": self.node.parameter}


class StaircaseTrialMaker(ChainTrialMaker):
    pass
