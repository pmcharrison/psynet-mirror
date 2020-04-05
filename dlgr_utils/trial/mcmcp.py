# pylint: disable=unused-argument,abstract-method

import random
from .chain import ChainTrialMaker, ChainTrial, ChainNode, ChainSource

class MCMCPTrial(ChainTrial):
    """
    A Network class for MCMCP. 
    
    Attributes
    ----------
    
    first_stimulus
        Definition of the first stimulus of the trial.
        This definition corresponds to a setting 
        of the chain's free parameters.
    
    second_stimulus
        Definition of the second stimulus of the trial,
        This definition corresponds to a setting 
        of the chain's free parameters.
    """
    __mapper_args__ = {"polymorphic_identity": "mcmcp_trial"}

    def make_definition(self, experiment, participant):
        """
        In MCMCP, a trial's definition is created by taking the 
        current state and the proposal from the source
        :class:`~dlgr_utils.trial.mcmcp.MCMCPNode`
        and adding a random ordering.
        
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
            plus the random ordering.
            
        """
        order = ["current_state", "proposal"]
        random.shuffle(order)
        definition = {
            "current_state": self.node.definition["current_state"],
            "proposal": self.node.definition["order"]
        }
        definition["ordered"] = [{
            "role": role,
            "value": definition[role]
        } for role in order]
        return definition
        
    @property 
    def first_stimulus(self):
        return self.definition["ordered"][0]["value"]
        
    @property 
    def second_stimulus(self):
        return self.definition["ordered"][1]["value"]

class MCMCPNode(ChainNode):
    """
    A Node class for MCMCP chains. 
    """
    
    __mapper_args__ = {"polymorphic_identity": "mcmcp_node"}

    def get_proposal(self, state, experiment, participant):
        """
        Implements the proposal function for the MCMP chain.
        
        Parameters
        ----------
        
        state
            The current state, with reference to which the proposal
            state should be constructed.
            
        experiment
            An instantiation of :class:`dlgr_utils.experiment.Experiment`,
            corresponding to the current experiment.
            
        participant
            An instantiation of :class:`dlgr_utils.participant.Participant`,
            corresponding to the current participant.
            
        Returns
        -------
        
        Object
            The proposal state.
        """
        raise NotImplementedError

    def summarise_trials(self, trials: list, experiment, participant):
        """
        (Abstract method, to be overridden)
        This method should summarise the answers to the provided trials.
        A default method is implemented for cases when there is
        just one trial per node; in this case, the method extracts and returns
        the parameter values for the chosen stimulus, following the standard
        definition of MCMCP. The method must be extended if it is to cope 
        with multiple trials per node.
        
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
        
        object
            The derived seed. Should be suitable for serialisation to JSON.
        """
        values = [trial.answer.value for trial in trials]
        if len(values) == 1:
            return values[0]
        raise NotImplementedError

    def create_definition_from_seed(self, seed, experiment, participant):
        return {
            "current_state": seed,
            "proposal": self.get_proposal(seed, experiment, participant)
        }

class MCMCPSource(ChainSource):
    """
    A Source class for MCMCP chains. 
    """
    
    __mapper_args__ = {"polymorphic_identity": "mcmcp_source"}

    def generate_seed(self, network, experiment, participant):
        raise NotImplementedError

class MCMCPTrialMaker(ChainTrialMaker):
    """
    A TrialMaker class for MCMCP chains;
    see the documentation for 
    :class:`~dlgr_utils.trial.chain.ChainTrialMaker`
    for usage instructions.
    """
    
    def finalise_trial(self, answer, trial, experiment, participant):
        """
        Modifies ``trial.answer`` so as to store three values:
        
        * The position of the chosen stimulus;
        * The role of the chosen stimulus (``"current_state"`` or ``"proposal"``);
        * The value of the parameters underlying the chosen stimulus.
        """
        # pylint: disable=unused-argument,no-self-use
        super().finalise_trial(answer, trial, experiment, participant)
        position = int(answer)
        trial.answer = {
            "position": position,
            "role": trial.definition["ordered"][position]["role"],
            "value": trial.definition["ordered"][position]["value"]
        }
