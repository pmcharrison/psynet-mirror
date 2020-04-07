# pylint: disable=unused-argument,abstract-method

from statistics import mean
from .chain import ChainNetwork, ChainTrialMaker, ChainTrial, ChainNode, ChainSource

import random

# pylint: disable=unused-import
import rpdb 

class GibbsNetwork(ChainNetwork):
    """
    A Network class for Gibbs sampler chains. 
    
    Attributes 
    ----------
    
    vector_length : int
        Must be overridden with the length of the free parameter vector
        that is manipulated during the Gibbs sampling procedure.
    """
    __mapper_args__ = {"polymorphic_identity": "gibbs_network"}
    
    vector_length = None
    
    def make_definition(self):
        return {}
        
    def random_sample(self, i: int):
        """
        (Abstract method, to be overridden)
        Randomly samples a new value for the ith element of the
        free parameter vector.
        This is used for initialising the participant's response options.
        
        Parameters
        ----------
        
        i 
            The index of the element that is being resampled.
            
        Returns
        -------
        
        float
            The new parameter value.
        """
        raise NotImplementedError

class GibbsTrial(ChainTrial):
    """
    A Trial class for Gibbs sampler chains. 
    
    Attributes
    ----------
    
    resample_free_parameter : bool
        If ``True`` (default), the starting value of the free parameter
        is resampled on each trial. Disable this behaviour
        by setting this parameter to ``False`` in the definition of 
        the custom :class:`~dlgr_utils.trial.gibbs.GibbsTrial` class.
    
    initial_vector : list
        The starting vector that is presented to the participant
        at the beginning of the trial.
    
    active_index : int
        The index of the parameter that the participant manipulates
        on this trial.
    
    updated_vector : list
        The updated vector after the participant has responded.
    """

    resample_free_parameter = True

    def make_definition(self, experiment, participant):
        """
        In the Gibbs sampler, a trial's definition is created by taking the 
        definition from the source
        :class:`~dlgr_utils.trial.gibbs.GibbsNode`
        and modifying it such that the free parameter has a randomised
        starting value. Note that different trials at the same
        :class:`~dlgr_utils.trial.gibbs.GibbsNode` will have the same 
        free parameters but different starting values for those free parameters.
        
        Parameters
        ----------
        
        experiment
            An instantiation of :class:`dlgr_utils.experiment.Experiment`,
            corresponding to the current experiment.
            
        participant
            Optional participant with which to associate the trial.
        
        Returns
        -------
        
        object
            The trial's definition, equal to the node's definition
            with the free parameter randomised.
            
        """
        vector = self.node.definition["vector"].copy()
        active_index = self.node.definition["active_index"]
        
        if self.resample_free_parameter:
            vector[active_index] = self.network.random_sample(active_index)
        
        definition = {
            "vector": vector,
            "active_index": active_index
        }
        
        return definition
        
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
    """
    A Node class for Gibbs sampler chains. 
    """
    __mapper_args__ = {"polymorphic_identity": "gibbs_node"}

    @staticmethod
    def parallel_mean(*vectors):
        return [mean(x) for x in zip(*vectors)]

    @staticmethod
    def get_unique(x):
        assert len(set(x)) == 1
        return x[0]

    def summarise_trials(self, trials: list, experiment, participant):
        """
        This method summarises the answers to the provided trials.
        The default method averages over all the provided parameter vectors,
        and will typically not need to be overridden.
        
        Parameters
        ----------
        trials
            Trials to be summarised. By default only trials that are completed
            (i.e. have received a response) and processed 
            (i.e. aren't waiting for an asynchronous process)
            are provided here.
            
        experiment
            An instantiation of :class:`dlgr_utils.experiment.Experiment`,
            corresponding to the current experiment.
            
        participant
            The participant who initiated the creation of the node.
            
        Returns
        -------
        
        dict
            A dictionary of the following form: 
            
            ::
            
                {
                    "vector": summary_vector,
                    "active_index": active_index
                }
                
            where ``summary_vector`` is the summary of all the vectors,
            and ``active_index`` is an integer identifying which was the
            free parameter.
        """
        updated_vectors = [trial.updated_vector for trial in trials]
        mean_updated_vector = self.parallel_mean(*updated_vectors)
        active_index = self.get_unique([trial.active_index for trial in trials])
        return {
            "vector": mean_updated_vector,
            "active_index": active_index
        }

    def create_definition_from_seed(self, seed, experiment, participant):
        """
        Creates a :class:`~dlgr_utils.trial.gibbs.GibbsNode` definition
        from the seed passed by the previous :class:`~dlgr_utils.trial.gibbs.GibbsNode`
        or :class:`~dlgr_utils.trial.gibbs.GibbsSource` in the chain. 
        The vector of parameters is preserved from the seed,
        but the 'active index' is increased by 1 modulo the length of the vector, 
        meaning that the next parameter in the vector is chosen as the current free parameter.
        This method will typically not need to be overridden.
        
            
        Returns
        -------
        
        dict
            A dictionary of the following form: 
            
            ::
            
                {
                    "vector": vector,
                    "active_index": new_index
                }
                
            where ``vector`` is the vector passed by the seed,
            and ``new_index`` identifies the position of the new free parameter.
        """
        vector = seed["vector"]
        dimension = len(vector)
        original_index = seed["active_index"]
        new_index = (original_index + 1) % dimension
        return {
            "vector": vector,
            "active_index": new_index
        }

class GibbsSource(ChainSource):
    """
    A Source class for Gibbs sampler chains. 
    """
    __mapper_args__ = {"polymorphic_identity": "gibbs_source"}

    def generate_seed(self, network, experiment, participant):
        """
        Generates the seed for the :class:`~dlgr_utils.trial.gibbs.GibbsSource`.
        By default the method samples the vector of parameters by repeatedly
        applying :meth:`~dlgr_utils.trial.gibbs.GibbsNetwork.random_sample`,
        and randomly chooses one of these parameters to be the free parameter (``"active_index"``).
        Note that the source itself doesn't receive trials, 
        and the first proper node in the chain will actually have 
        the free parameter after this one (i.e. if there are 5 elements in the vector,
        and the :class:`~dlgr_utils.trial.gibbs.GibbsSource` has an ``"active_index"`` of 
        2, then the first trials in the chain will have an ``"active_index"`` of 3.
        This method will not normally need to be overridden.
        
        Parameters
        ----------
        
        network
            The network with which the :class:`~dlgr_utils.trial.gibbs.GibbsSource` is associated.
    
        experiment
            An instantiation of :class:`dlgr_utils.experiment.Experiment`,
            corresponding to the current experiment.
        
        participant:
            An instantiation of :class:`dlgr_utils.participant.Participant`,
            corresponding to the current participant.
            
        Returns
        -------
        
        dict
            A dictionary of the following form: 
            
            ::
            
                {
                    "vector": vector,
                    "active_index": active_index
                }
                
            where ``vector`` is the initial vector
            and ``active_index`` identifies the position of the free parameter.        
        """
        if network.vector_length is None:
            raise ValueError("network.vector_length must not be None. Did you forget to set it?")
        return {
            "vector": [network.random_sample(i) for i in range(network.vector_length)],
            "active_index": random.randint(0, network.vector_length),
        }
 

class GibbsTrialMaker(ChainTrialMaker):
    """
    A TrialMaker class for Gibbs sampler chains;
    see the documentation for 
    :class:`~dlgr_utils.trial.chain.ChainTrialMaker`
    for usage instructions.
    """
