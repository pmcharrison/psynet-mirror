# pylint: disable=unused-argument,abstract-method

from statistics import mean
from .chain import ChainTrialMaker, ChainTrial, ChainNode, ChainSource

import rpdb 

class GibbsTrial(ChainTrial):
    def show_trial(self, experiment, participant):
        """
        Should return a Page object that returns an answer that can be stored in Trial.answer.
        """
        raise NotImplementedError

    def make_definition(self, experiment, participant):
        # TODO : randomise the starting point
        return self.node.definition

    @property 
    def initial_vector(self):
        return self.definition["vector"]

    @property
    def active_index(self):
        return self.definition["active_index"]

    @property
    def updated_vector(self):
        new = self.initial_vector.copy()
        new[self.active_index] = self.answer
        return new

class GibbsNode(ChainNode):
    __mapper_args__ = {"polymorphic_identity": "gibbs_node"}

    @staticmethod
    def parallel_mean(*vectors):
        return [mean(x) for x in zip(*vectors)]

    @staticmethod
    def get_unique(x):
        assert len(set(x)) == 1
        return x[0]

    def summarise_trials(self, trials, experiment, participant):
        """This function should summarise the answers to the provided trials."""
        updated_vectors = [trial.updated_vector for trial in trials]
        mean_updated_vector = self.parallel_mean(*updated_vectors)
        active_index = self.get_unique([trial.active_index for trial in trials])
        return {
            "vector": mean_updated_vector,
            "active_index": active_index
        }

    def create_definition_from_seed(self, seed, experiment, participant):
        vector = seed["vector"]
        dimension = len(vector)
        original_index = seed["active_index"]
        new_index = (original_index + 1) % dimension
        return {
            **seed,
            "vector": vector,
            "active_index": new_index
        }

class GibbsSource(ChainSource):
    __mapper_args__ = {"polymorphic_identity": "gibbs_source"}

    def generate_seed(self, network, experiment, participant):
        raise NotImplementedError

class GibbsTrialMaker(ChainTrialMaker):
    def test_recruit(self, experiment):
        assert False
        return True
    
    recruit_criteria = {
        **ChainTrialMaker.recruit_criteria,
        "test": test_recruit
    }
