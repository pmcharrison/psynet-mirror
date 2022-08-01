import random
import warnings
from typing import Optional

from dallinger import db
from sqlalchemy import Column, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.sql.expression import not_

from ..field import VarStore, claim_field, claim_var, extra_var, register_extra_var
from ..page import wait_while
from ..utils import get_logger, negate
from .main import (
    HasDefinition,
    NetworkTrialMaker,
    Trial,
    TrialNetwork,
    TrialNode,
    TrialSource,
)

logger = get_logger()


class HasSeed:
    # Mixin class that provides a 'seed' slot.
    # See https://docs.sqlalchemy.org/en/14/orm/inheritance.html#resolving-column-conflicts
    @declared_attr
    def seed(cls):
        return cls.__table__.c.get(
            "seed", Column(JSONB, server_default="{}", default=lambda: {})
        )

    __extra_vars__ = {}
    register_extra_var(__extra_vars__, "seed", field_type=dict)


class ChainNetwork(TrialNetwork):
    """
    Implements a network in the form of a chain.
    Intended for use with :class:`~psynet.trial.chain.ChainTrialMaker`.
    Typically the user won't have to override anything here,
    but they can optionally override :meth:`~psynet.trial.chain.ChainNetwork.validate`.

    Parameters
    ----------

    source_class
        The class object for network sources. A source is the 'seed' for a network,
        providing some data which is somehow propagated to other nodes.

    phase
        Arbitrary label for this phase of the experiment, e.g.
        "practice", "train", "test".

    experiment
        An instantiation of :class:`psynet.experiment.Experiment`,
        corresponding to the current experiment.

    chain_type
        Either ``"within"`` for within-participant chains,
        or ``"across"`` for across-participant chains.

    trials_per_node
        Number of satisfactory trials to be received by the last node
        in the chain before another chain will be added.
        Most paradigms have this equal to 1.

    target_num_nodes
        Indicates the target number of nodes for that network.
        In a network with one trial per node, the total number of nodes will generally
        be one greater than the total number of trials. This is because
        we start with one node, representing the random starting location of the
        chain, and each new trial takes us to a new node.

    participant
        Optional participant with which to associate the network.

    id_within_participant
        If ``participant is not None``, then this provides an optional ID for the network
        that is unique within a given participant.

    Attributes
    ----------

    target_num_trials : int or None
        Indicates the target number of trials for that network.
        Left empty by default, but can be set by custom ``__init__`` functions.

    phase : str
        Arbitrary label for this phase of the experiment, e.g.
        "practice", "train", "test".
        Set by default in the ``__init__`` function.

    awaiting_async_process : bool
        Whether the network is currently waiting for an asynchronous process to complete.

    earliest_async_process_start_time : Optional[datetime]
        Time at which the earliest pending async process was called.

    num_nodes : int
        Returns the number of non-failed nodes in the network.

    num_completed_trials : int
        Returns the number of completed and non-failed trials in the network
        (irrespective of asynchronous processes, but excluding repeat trials).

    var : :class:`~psynet.field.VarStore`
        A repository for arbitrary variables; see :class:`~psynet.field.VarStore` for details.

    participant_id : int
        The ID of the associated participant, or ``None`` if there is no such participant.
        Set by default in the ``__init__`` function.

    id_within_participant
        If ``participant is not None``, then this provides an optional ID for the network
        that is unique within a given participant.
        Set by default in the ``__init__`` function.

    chain_type
        Either ``"within"`` for within-participant chains,
        or ``"across"`` for across-participant chains.
        Set by default in the ``__init__`` function.

    trials_per_node
        Number of satisfactory trials to be received by the last node
        in the chain before another chain will be added.
        Most paradigms have this equal to 1.
        Set by default in the ``__init__`` function.
    """

    # pylint: disable=abstract-method
    __extra_vars__ = TrialNetwork.__extra_vars__.copy()

    participant_id = claim_field("participant_id", __extra_vars__, int)
    id_within_participant = claim_field("id_within_participant", __extra_vars__, int)

    participant_group = claim_var("participant_group", __extra_vars__)
    chain_type = claim_var("chain_type", __extra_vars__)
    trials_per_node = claim_var("trials_per_node", __extra_vars__)
    definition = claim_var("definition", __extra_vars__)

    # Note - the <details> slot is occupied by VarStore.

    def __init__(
        self,
        trial_maker_id: str,
        source_class,
        phase: str,
        experiment,
        chain_type: str,
        trials_per_node: int,
        target_num_nodes: int,
        participant=None,
        id_within_participant: Optional[int] = None,
    ):
        super().__init__(trial_maker_id, phase, experiment)
        db.session.add(self)
        db.session.commit()

        if participant is not None:
            self.id_within_participant = id_within_participant
            self.participant_id = participant.id

        self.chain_type = chain_type
        self.trials_per_node = trials_per_node
        self.target_num_nodes = target_num_nodes
        # The last node in the chain doesn't receive any trials
        self.target_num_trials = (target_num_nodes - 1) * trials_per_node
        self.definition = self.make_definition()
        self.participant_group = self.get_participant_group()
        self.add_source(source_class, experiment, participant)

        self.validate()

        experiment.save()

    def get_participant_group(self):
        if isinstance(self.definition, dict):
            try:
                return self.definition["participant_group"]
            except KeyError:
                pass
        return "default"

    def validate(self):
        """
        Runs at the end of the constructor function to check that the
        network object has a legal structure. This can be useful for
        checking that the user hasn't passed illegal argument values.
        """
        pass

    def make_definition(self):
        """
        Derives the definition for the network.
        This definition represents some collection of attributes
        that is shared by all nodes/trials in a network,
        but that may differ between networks.

        Suppose one wishes to have multiple networks in the experiment,
        each characterised by a different value of an attribute
        (e.g. a different color).
        One approach would be to sample randomly; however, this would not
        guarantee an even distribution of attribute values.
        In this case, a better approach is to use the
        :meth:`psynet.trial.chain.ChainNetwork.balance_across_networks`
        method, as follows:

        ::

            colors = ["red", "green", "blue"]
            return {
                "color": self.balance_across_networks(colors)
            }

        See :meth:`psynet.trial.chain.ChainNetwork.balance_across_networks`
        for details on how this balancing works.

        Returns
        -------

        object
            By default this returns an empty dictionary,
            but this can be customised by subclasses.
            The object should be suitable for serialisation to JSON.
        """
        return {}

    def balance_across_networks(self, values: list):
        """
        Chooses a value from a list, with choices being balanced across networks.
        Relies on the fact that network IDs are guaranteed to be consecutive.
        sequences of integers.

        Suppose we wish to assign our networks to colors,
        and we want to balance color assignment across networks.
        We might write the following:

        ::

            colors = ["red", "green", "blue"]
            chosen_color = self.balance_across_networks(colors)

        In across-participant chain designs,
        :meth:`~psynet.trial.chain.ChainNetwork.balance_across_networks`
        will ensure that the distribution of colors is maximally uniform across
        the experiment by assigning
        the first network to red, the second network to green, the third to blue,
        then the fourth to red, the fifth to green, the sixth to blue,
        and so on. This is achieved by referring to the network's
        :attr:`~psynet.trial.chain.ChainNetwork.id`
        attribute.
        In within-participant chain designs,
        the same method is used but within participants,
        so that each participant's first network is assigned to red,
        their second network to green,
        their third to blue,
        then their fourth, fifth, and sixth to red, green, and blue respectively.

        Parameters
        ----------

        values
            The list of values from which to choose.

        Returns
        -------

        Object
            An object from the provided list.
        """
        if self.chain_type == "across":
            id_to_use = self.id
        elif self.chain_type == "within":
            id_to_use = self.id_within_participant
        else:
            raise RuntimeError(f"Unexpected chain_type: {self.chain_type}")

        return values[id_to_use % len(values)]

    @property
    def target_num_nodes(self):
        # Subtract 1 to account for the source
        return self.max_size - 1

    @target_num_nodes.setter
    def target_num_nodes(self, target_num_nodes):
        self.max_size = target_num_nodes + 1

    @property
    def num_nodes(self):
        return ChainNode.query.filter_by(network_id=self.id, failed=False).count()

    @property
    def degree(self):
        if self.num_nodes == 0:
            return 0
        return (
            # pylint: disable=no-member
            db.session.query(func.max(ChainNode.degree))
            .filter(ChainNode.network_id == self.id, ChainNode.failed.is_(False))
            .scalar()
        )

    @property
    def source(self):
        return ChainSource.query.filter_by(network_id=self.id).one()

    @property
    def head(self):
        if self.num_nodes == 0:
            return self.source
        else:
            degree = self.degree
            return self.get_node_with_degree(degree)

    def get_node_with_degree(self, degree):
        assert degree >= 0
        if degree == 0:
            return self.source
        nodes = (
            ChainNode.query.filter_by(network_id=self.id, failed=False)
            .order_by(ChainNode.id)
            .all()
        )

        # This cannot be included in the SQL call because not all Node objects
        # have the property `degree`.
        # This can cause an error once enough SQLAlchemy Node classes have been
        # registered (more than 6 changes the order of execution and so
        # SQL tries to cast property1 to int even for Node classes that aren't ChainNodes.
        nodes = [n for n in nodes if n.degree == degree]

        # This deals with the case where somehow we've ended up with multiple
        # nodes at the same degree.
        first_node = nodes[0]
        other_nodes = nodes[1:]
        for node in other_nodes:
            node.fail(reason=f"duplicate_node_at_degree_{node.degree}")
        return first_node

    def add_node(self, node):
        if node.degree > 0:
            previous_head = self.get_node_with_degree(node.degree - 1)
            previous_head.connect(whom=node)
            previous_head.child = node
        if self.num_nodes >= self.target_num_nodes:
            self.full = True

    def add_source(self, source_class, experiment, participant=None):
        source = source_class(self, experiment, participant)
        db.session.add(source)
        self.add_node(source)
        db.session.commit()

    @property
    def num_trials_still_required(self):
        assert self.target_num_trials is not None
        if self.full:
            return 0
        else:
            return self.target_num_trials - self.num_completed_trials

    def fail_async_processes(self, reason):
        super().fail_async_processes(reason)
        self.head.fail(reason=reason)


class ChainNode(TrialNode, HasSeed, HasDefinition):
    """
    Represents a node in a chain network.
    In an experimental context, the node represents a state in the experiment;
    in particular, the last node in the chain represents a current state
    in the experiment.

    This class is intended for use with :class:`~psynet.trial.chain.ChainTrialMaker`.
    It subclasses :class:`dallinger.models.Node`.

    The most important attribute is :attr:`~psynet.trial.chain.ChainNode.definition`.
    This is the core information that represents the current state of the node.
    In a transmission chain of drawings, this might be an (encoded) drawing;
    in a Markov Chain Monte Carlo with People paradigm, this might be the current state
    from the proposal is sampled.

    The user is required to override the following abstract methods:

    * :meth:`~psynet.trial.chain.ChainNode.create_definition_from_seed`,
      which creates a node definition from the seed passed from the previous
      source or node in the chain;

    * :meth:`~psynet.trial.chain.ChainNode.summarize_trials`,
      which summarizes the trials at a given node to produce a seed that can
      be passed to the next node in the chain.

    Parameters
    ----------

    seed
        The seed which is used to initialize the node, potentially stochastically.
        This seed typically comes from either a :class:`~psynet.trial.chain.ChainSource`
        or from another :class:`~psynet.trial.chain.ChainNode`
        via the :meth:`~psynet.trial.chain.ChainNode.create_seed` method.
        For example, in a transmission chain of drawings, the seed might be
        a serialised version of the last drawn image.

    degree
        The position of the node in the chain,
        where 0 indicates the source,
        where 1 indicates the first node,
        2 the second node, and so on.

    network
        The network with which the node is to be associated.

    experiment
        An instantiation of :class:`psynet.experiment.Experiment`,
        corresponding to the current experiment.

    propagate_failure
        If ``True``, the failure of a trial is propagated to other
        parts of the experiment (the nature of this propagation is left up
        to the implementation).

    participant
        Optional participant with which to associate the node.

    Attributes
    ----------

    degree
        See the ``__init__`` function.

    child_id
        See the ``__init__`` function.

    seed
        See the ``__init__`` function.

    definition
        This is the core information that represents the current state of the node.
        In a transmission chain of drawings, this might be an (encoded) drawing;
        in a Markov Chain Monte Carlo with People paradigm, this might be the current state
        from the proposal is sampled.
        It is set by the :meth:`~psynet.trial.chain.ChainNode:create_definition_from_seed` method.

    propagate_failure
        See the ``__init__`` function.

    var : :class:`~psynet.field.VarStore`
        A repository for arbitrary variables; see :class:`~psynet.field.VarStore` for details.

    source
        The source of the chain, if one exists.
        Should be an object of class :class:`~psynet.trial.chain.ChainSource`.

    child
        The node's child (i.e. direct descendant) in the chain, or
        ``None`` if no child exists.

    phase
        Arbitrary label for this phase of the experiment, e.g.
        "practice", "train", "test".
        Set from :attr:`psynet.trial.chain.ChainNetwork.trials_per_node`.

    target_num_trials
        The target number of trials for the node,
        set from :attr:`psynet.trial.chain.ChainNetwork.trials_per_node`.

    ready_to_spawn
        Returns ``True`` if the node is ready to spawn a child.
        Not intended for overriding.

    complete_and_processed_trials
        Returns all completed trials associated with the node,
        excluding those that are awaiting some asynchronous processing.
        excludes failed nodes.

    completed_trials
        Returns all completed trials associated with the node.
        Excludes failed nodes and repeat trials.

    num_completed_trials
        Counts the number of completed trials associated with the node.
        Excludes failed nodes and repeat_trials.

    num_viable_trials
        Returns all viable trials associated with the node,
        i.e. all trials that have not failed.
    """

    __extra_vars__ = {
        **HasSeed.__extra_vars__.copy(),
        **HasDefinition.__extra_vars__.copy(),
        **TrialNode.__extra_vars__.copy(),
    }

    def __init__(
        self,
        seed,
        degree: int,
        network,
        experiment,
        propagate_failure: bool,
        participant=None,
    ):
        # pylint: disable=unused-argument
        super().__init__(network=network, participant=participant)
        self.seed = seed
        self.degree = degree
        self.definition = self.create_definition_from_seed(
            seed, experiment, participant
        )
        self.propagate_failure = propagate_failure

    def create_definition_from_seed(self, seed, experiment, participant):
        """
        Creates a node definition from a seed.
        The seed comes from the previous state in the chain, which
        will be either a :class:`~psynet.trial.chain.ChainSource`
        or a :class:`~psynet.trial.chain.ChainNode`.
        In many cases (e.g. iterated reproduction) the definition
        will be trivially equal to the seed,
        but in some cases we may introduce some kind of stochastic alteration
        to produce the definition.

        Parameters
        ----------

        seed : object
            The seed, passed from the previous state in the chain.

        experiment
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.

        participant
            The participant who initiated the creation of the node.

        Returns
        -------

        object
            The derived definition. Should be suitable for serialisation to JSON.
        """
        raise NotImplementedError

    def summarize_trials(self, trials: list, experiment, participant):
        """
        Summarizes the trials at the node to produce a seed that can
        be passed to the next node in the chain.

        Parameters
        ----------

        trials
            Trials to be summarized. By default only trials that are completed
            (i.e. have received a response) and processed
            (i.e. aren't waiting for an asynchronous process)
            are provided here.

        experiment
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.

        participant
            The participant who initiated the creation of the node.

        Returns
        -------

        object
            The derived seed. Should be suitable for serialisation to JSON.
        """
        raise NotImplementedError

    def create_seed(self, experiment, participant):
        trials = self.completed_and_processed_trials.all()
        return self.summarize_trials(trials, experiment, participant)

    degree = claim_field("degree", __extra_vars__, int)
    child_id = claim_field("child_id", __extra_vars__, int)

    propagate_failure = claim_var("propagate_failure", __extra_vars__)

    # VarStore occuppies the <details> slot.
    @property
    def var(self):
        return VarStore(self)

    @property
    def source(self):
        return self.network.source

    @property
    def child(self):
        if self.child_id is None:
            return None
        return ChainNode.query.filter_by(id=self.child_id).one()

    @child.setter
    def child(self, child):
        self.child_id = child.id

    @property
    @extra_var(__extra_vars__)
    def phase(self):
        return self.network.phase

    @property
    def target_num_trials(self):
        return self.network.trials_per_node

    @property
    def ready_to_spawn(self):
        return self.reached_target_num_trials()

    @property
    def completed_and_processed_trials(self):
        return Trial.query.filter_by(
            origin_id=self.id,
            failed=False,
            complete=True,
            finalized=True,
            is_repeat_trial=False,
        )

    @property
    def _query_completed_trials(self):
        return Trial.query.filter_by(
            origin_id=self.id, failed=False, complete=True, is_repeat_trial=False
        )

    @property
    def completed_trials(self):
        return self._query_completed_trials.all()

    @property
    def num_completed_trials(self):
        return self._query_completed_trials.count()

    @property
    def num_viable_trials(self):
        return Trial.query.filter_by(
            origin_id=self.id, failed=False, is_repeat_trial=False
        ).count()

    def reached_target_num_trials(self):
        return self.completed_and_processed_trials.count() >= self.target_num_trials

    @property
    def failure_cascade(self):
        to_fail = []
        if self.propagate_failure:
            to_fail.append(self.infos)
            if self.child:
                to_fail.append(lambda: [self.child])
        return to_fail

    def fail(self, reason=None):
        """
        Marks the node as failed.

        If a `reason` argument is passed, this will be stored in
        :attr:`~dallinger.models.SharedMixin.failed_reason`.
        """
        if not self.failed:
            super().fail(reason=reason)


class ChainSource(TrialSource, HasSeed):
    """
    Represents a source in a chain network.
    The source provides the seed from which the rest of the chain is ultimately derived.

    This class is intended for use with :class:`~psynet.trial.chain.ChainTrialMaker`.
    It subclasses :class:`dallinger.nodes.Source`.

    The most important attribute is :attr:`~psynet.trial.chain.ChainSource.definition`.
    This is the core information that represents the current state of the node.
    In a transmission chain of drawings, this might be the initial drawing
    that begins the transmission chain.

    The user is required to override the following abstract method:

    * :meth:`~psynet.trial.chain.ChainSource.generate_seed`,
      which generates a seed for the :class:`~psynet.trial.chain.ChainSource`
      which will then be stored in the :attr:`~psynet.trial.chain.ChainSource.seed` attribute.

    Parameters
    ----------

    network
        The network with which the node is to be associated.

    experiment
        An instantiation of :class:`psynet.experiment.Experiment`,
        corresponding to the current experiment.

    participant
        Optional participant with which to associate the node.

    Attributes
    ----------

    degree
        The degree of a :class:`~psynet.trial.chain.ChainSource` object is always 0.

    seed
        The seed that is passed to the next node in the chain.
        Created by :meth:`~psynet.trial.chain.ChainSource.generate_seed`.

    var : :class:`~psynet.field.VarStore`
        A repository for arbitrary variables; see :class:`~psynet.field.VarStore` for details.

    phase
        Arbitrary label for this phase of the experiment, e.g.
        "practice", "train", "test".
        Set from :attr:`psynet.trial.chain.ChainNetwork.phase`.

    ready_to_spawn
        Always returns ``True`` for :class:`~psynet.trial.chain.ChainSource` objects.
    """

    # pylint: disable=abstract-method
    __extra_vars__ = {
        **TrialSource.__extra_vars__.copy(),
        **HasSeed.__extra_vars__.copy(),
    }

    ready_to_spawn = True
    degree = 0

    def __init__(self, network, experiment, participant):
        super().__init__(network, participant)
        self.seed = self.generate_seed(network, experiment, participant)

    @property
    @extra_var(__extra_vars__)
    def degree(self):
        return 0

    @property
    @extra_var(__extra_vars__)
    def phase(self):
        return self.network.phase

    @property
    def var(self):  # occupies the <details> attribute
        return VarStore(self)

    def fail(self, reason=None):
        """
        Marks the source node as failed.

        If a `reason` argument is passed, this will be stored in
        :attr:`~dallinger.models.SharedMixin.failed_reason`.
        """
        if not self.failed:
            super().fail(reason=reason)

    def create_seed(self, experiment, participant):
        # pylint: disable=unused-argument
        return self.seed

    def generate_seed(self, network, experiment, participant):
        """
        Generates a seed for the :class:`~psynet.trial.chain.ChainSource` and
        correspondingly for the :class:`~psynet.trial.chain.ChainNetwork`.

        Parameters
        ----------

        network
            The network to which the :class:`~psynet.trial.chain.ChainSource` belongs.

        experiment
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.

        participant
            The associated participant, if relevant.

        Returns
        -------

        object
            The generated seed. It must be suitable for serialisation to JSON.
        """
        raise NotImplementedError


class ChainTrial(Trial):
    """
    Represents a trial in a :class:`~psynet.trial.chain.ChainNetwork`.
    The user is expected to override the following methods:

    * :meth:`~psynet.trial.chain.ChainTrial.make_definition`,
      responsible for deciding on the content of the trial.
    * :meth:`~psynet.trial.chain.ChainTrial.show_trial`,
      determines how the trial is turned into a webpage for presentation to the participant.
    * :meth:`~psynet.trial.chain.ChainTrial.show_feedback`.
      defines an optional feedback page to be displayed after the trial.

    The user must also override the ``time_estimate`` class attribute,
    providing the estimated duration of the trial in seconds.
    This is used for predicting the participant's bonus payment
    and for constructing the progress bar.

    The user may also wish to override the
    :meth:`~psynet.trial.chain.ChainTrial.async_post_trial` method
    if they wish to implement asynchronous trial processing.

    This class subclasses the `~psynet.trial.main.Trial` class,
    which in turn subclasses the :class:`~dallinger.models.Info` class from Dallinger,
    hence it can be found in the ``Info`` table in the database.
    It inherits these class's methods, which the user is welcome to use
    if they seem relevant.

    Instances can be retrieved using *SQLAlchemy*; for example, the
    following command retrieves the ``ChainTrial`` object with an ID of 1:

    ::

        ChainTrial.query.filter_by(id=1).one()

    Parameters
    ----------

    experiment:
        An instantiation of :class:`psynet.experiment.Experiment`,
        corresponding to the current experiment.

    node:
        An object of class :class:`dallinger.models.Node` to which the
        :class:`~dallinger.models.Trial` object should be attached.
        Complex experiments are often organised around networks of nodes,
        but in the simplest case one could just make one :class:`~dallinger.models.Network`
        for each type of trial and one :class:`~dallinger.models.Node` for each participant,
        and then assign the :class:`~dallinger.models.Trial`
        to this :class:`~dallinger.models.Node`.
        Ask us if you want to use this simple use case - it would be worth adding
        it as a default to this implementation, but we haven't done that yet,
        because most people are using more complex designs.

    participant:
        An instantiation of :class:`psynet.participant.Participant`,
        corresponding to the current participant.

    propagate_failure : bool
        Whether failure of a trial should be propagated to other
        parts of the experiment depending on that trial
        (for example, subsequent parts of a transmission chain).

    run_async_post_trial : bool
        Set this to ``True`` if you want the :meth:`~psynet.trial.main.Trial.async_post_trial`
        method to run after the user responds to the trial.

    Attributes
    ----------

    time_estimate : numeric
        The estimated duration of the trial (including any feedback), in seconds.
        This should generally correspond to the (sum of the) ``time_estimate`` parameters in
        the page(s) generated by ``show_trial``, plus the ``time_estimate`` parameter in
        the page generated by ``show_feedback`` (if defined).
        This is used for predicting the participant's bonus payment
        and for constructing the progress bar.

    node
        The class:`dallinger.models.Node` to which the :class:`~dallinger.models.Trial`
        belongs.

    participant_id : int
        The ID of the associated participant.
        The user should not typically change this directly.
        Stored in ``property1`` in the database.

    complete : bool
        Whether the trial has been completed (i.e. received a response
        from the participant). The user should not typically change this directly.
        Stored in ``property2`` in the database.

    answer : Object
        The response returned by the participant. This is serialised
        to JSON, so it shouldn't be too big.
        The user should not typically change this directly.
        Stored in ``details`` in the database.

    awaiting_async_process : bool
        Whether the trial is waiting for some asynchronous process
        to complete (e.g. to synthesise audiovisual material).
        The user should not typically change this directly.

    earliest_async_process_start_time : Optional[datetime]
        Time at which the earliest pending async process was called.

    source
        The :class:`~psynet.trial.chain.ChainSource of the
        :class:`~psynet.trial.chain.ChainNetwork`
        to which the :class:`~psynet.trial.chain.ChainTrial` belongs.

    phase : str
        Arbitrary label for this phase of the experiment, e.g.
        "practice", "train", "test".
        Pulled from the :attr:`~psynet.trial.chain.ChainTrial.node` attribute.

    propagate_failure : bool
        Whether failure of a trial should be propagated to other
        parts of the experiment depending on that trial
        (for example, subsequent parts of a transmission chain).

    var : :class:`~psynet.field.VarStore`
        A repository for arbitrary variables; see :class:`~psynet.field.VarStore` for details.

    definition : Object
        An arbitrary Python object that somehow defines the content of
        a trial. Often this will be a dictionary comprising a few
        named parameters.
        The user should not typically change this directly,
        as it is instead determined by
        :meth:`~psynet.trial.main.Trial.make_definition`.

    """

    # pylint: disable=abstract-method
    __extra_vars__ = Trial.__extra_vars__.copy()

    @property
    @extra_var(__extra_vars__)
    def degree(self):
        return self.node.degree

    @property
    @extra_var(__extra_vars__)
    def phase(self):
        return self.node.phase

    @property
    @extra_var(__extra_vars__)
    def node_id(self):
        return self.origin_id

    @property
    def node(self):
        return self.origin

    @property
    def source(self):
        return self.node.source

    @property
    def failure_cascade(self):
        to_fail = []
        if self.propagate_failure:
            if self.child:
                to_fail.append(lambda: [self.child])
        return to_fail

    def fail(self, reason=None):
        """
        Marks a trial as failed. Failing a trial means that it is somehow
        excluded from certain parts of the experiment logic, for example
        not counting towards data collection quotas, or not contributing
        towards latter parts of a transmission chain.

        The original fail function from the
        :class:`~dallinger.models.Info` class
        throws an error if the object is already failed,
        but this behaviour is disabled here.
        """
        if not self.failed:
            super().fail(reason=reason)


class ChainTrialMaker(NetworkTrialMaker):
    """
    Administers a sequence of trials in a chain-based paradigm.
    This trial maker is suitable for implementing paradigms such as
    Markov Chain Monte Carlo with People, iterated reproduction, and so on.
    It is intended for use with the following helper classes,
    which should be customised for the particular paradigm:

    * :class:`~psynet.trial.chain.ChainNetwork`;
      a special type of :class:`~psynet.trial.main.TrialNetwork`

    * :class:`~psynet.trial.chain.ChainNode`;
      a special type of :class:`~dallinger.models.Node`

    * :class:`~psynet.trial.chain.ChainTrial`;
      a special type of :class:`~psynet.trial.main.NetworkTrial`

    * :class:`~psynet.trial.chain.ChainSource`;
      a special type of :class:`~dallinger.nodes.Source`, corresponding
      to the initial state of the network.

    A chain is initialized with a :class:`~psynet.trial.chain.ChainSource` object.
    This :class:`~psynet.trial.chain.ChainSource` object provides
    the initial seed to the chain.
    The :class:`~psynet.trial.chain.ChainSource` object is followed
    by a series of :class:`~psynet.trial.chain.ChainNode` objects
    which are generated through the course of the experiment.
    The last :class:`~psynet.trial.chain.ChainNode` in the chain
    represents the current state of the chain, and it determines the
    properties of the next trials to be drawn from that chain.
    A new :class:`~psynet.trial.chain.ChainNode` object is generated once
    sufficient :class:`~psynet.trial.chain.ChainTrial` objects
    have been created for that :class:`~psynet.trial.chain.ChainNode`.
    There can be multiple chains in an experiment, with these chains
    either being owned by individual participants ("within-participant" designs)
    or shared across participants ("across-participant" designs).

    Parameters
    ----------

    network_class
        The class object for the networks used by this maker.
        This should subclass :class:`~psynet.trial.chain.ChainNetwork`.

    node_class
        The class object for the networks used by this maker.
        This should subclass :class:`~psynet.trial.chain.ChainNode`.

    source_class
        The class object for sources
        (should subclass :class:`~psynet.trial.chain.ChainSource`).

    trial_class
        The class object for trials administered by this maker
        (should subclass :class:`~psynet.trial.chain.ChainTrial`).

    phase
        Arbitrary label for this phase of the experiment, e.g.
        "practice", "train", "test".

    chain_type
        Either ``"within"`` for within-participant chains,
        or ``"across"`` for across-participant chains.

    num_trials_per_participant
        Maximum number of trials that each participant may complete;
        once this number is reached, the participant will move on
        to the next stage in the timeline.

    num_chains_per_participant
        Number of chains to be created for each participant;
        only relevant if ``chain_type="within"``.

    num_chains_per_experiment
        Number of chains to be created for the entire experiment;
        only relevant if ``chain_type="across"``.

    num_iterations_per_chain
        Specifies chain length in terms of the
        number of data-collection iterations that are required to complete a chain.
        The number of successful participant trials required to complete the chain then
        corresponds to ``trials_per_node * num_iterations_per_chain``.
        Previously chain length was specified using the now-deprecated argument ``num_nodes_per_chain``.

    num_nodes_per_chain
        [DEPRECATED; new code should use ``num_iterations_per_chain`` and leave this argument empty.]
        Maximum number of nodes in the chain before the chain is marked as full and no more nodes will be added.
        The final node receives no participant trials, but instead summarizes the state of the network.
        So, ``num_nodes_per_chain`` is equal to ``1 + num_iterations_per_chain``.

    trials_per_node
        Number of satisfactory trials to be received by the last node
        in the chain before another chain will be added.
        Most paradigms have this equal to 1.

    balance_across_chains
        Whether trial selection should be actively balanced across chains,
        such that trials are preferentially sourced from chains with
        fewer valid trials.

    check_performance_at_end
        If ``True``, the participant's performance
        is evaluated at the end of the series of trials.

    check_performance_every_trial
        If ``True``, the participant's performance
        is evaluated after each trial.

    recruit_mode
        Selects a recruitment criterion for determining whether to recruit
        another participant. The built-in criteria are ``"num_participants"``
        and ``"num_trials"``, though the latter requires overriding of
        :attr:`~psynet.trial.main.TrialMaker.num_trials_still_required`.

    target_num_participants
        Target number of participants to recruit for the experiment. All
        participants must successfully finish the experiment to count
        towards this quota. This target is only relevant if
        ``recruit_mode="num_participants"``.

    fail_trials_on_premature_exit
        If ``True``, a participant's trials are marked as failed
        if they leave the experiment prematurely.
        Defaults to ``False`` because failing such trials can end up destroying
        large parts of existing chains.

    fail_trials_on_participant_performance_check
        If ``True``, a participant's trials are marked as failed
        if the participant fails a performance check.
        Defaults to ``False`` because failing such trials can end up destroying
        large parts of existing chains.

    propagate_failure
        If ``True``, the failure of a trial is propagated to other
        parts of the experiment (the nature of this propagation is left up
        to the implementation).

    num_repeat_trials
        Number of repeat trials to present to the participant. These trials
        are typically used to estimate the reliability of the participant's
        responses.
        Defaults to ``0``.

    wait_for_networks
        If ``True``, then the participant will be made to wait if there are
        still more networks to participate in, but these networks are pending asynchronous processes.

    allow_revisiting_networks_in_across_chains : bool
        If this is set to ``True``, then participants can revisit the same network
        in across-participant chains. The default is ``False``.

    Attributes
    ----------

    check_timeout_interval_sec : float
        How often to check for trials that have timed out, in seconds (default = 30).
        Users are invited to override this.

    response_timeout_sec : float
        How long until a trial's response times out, in seconds (default = 60)
        (i.e. how long PsyNet will wait for the participant's response to a trial).
        This is a lower bound on the actual timeout
        time, which depends on when the timeout daemon next runs,
        which in turn depends on :attr:`~psynet.trial.main.TrialMaker.check_timeout_interval_sec`.
        Users are invited to override this.

    async_timeout_sec : float
        How long until an async process times out, in seconds (default = 300).
        This is a lower bound on the actual timeout
        time, which depends on when the timeout daemon next runs,
        which in turn depends on :attr:`~psynet.trial.main.TrialMaker.check_timeout_interval_sec`.
        Users are invited to override this.

    network_query : sqlalchemy.orm.Query
        An SQLAlchemy query for retrieving all networks owned by the current trial maker.
        Can be used for operations such as the following: ``self.network_query.count()``.

    num_networks : int
        Returns the number of networks owned by the trial maker.

    networks : list
        Returns the networks owned by the trial maker.

    performance_check_threshold : float
        Score threshold used by the default performance check method, defaults to 0.0.
        By default, corresponds to the minimum proportion of non-failed trials that
        the participant must achieve to pass the performance check.

    end_performance_check_waits : bool
        If ``True`` (default), then the final performance check waits until all trials no
        longer have any pending asynchronous processes.
    """

    def __init__(
        self,
        *,
        id_,
        network_class,
        node_class,
        source_class,
        trial_class,
        phase: str,
        chain_type: str,
        num_trials_per_participant: int,
        num_chains_per_participant: Optional[int],
        num_chains_per_experiment: Optional[int],
        trials_per_node: int,
        balance_across_chains: bool,
        check_performance_at_end: bool,
        check_performance_every_trial: bool,
        recruit_mode: str,
        target_num_participants=Optional[int],
        num_iterations_per_chain: Optional[int] = None,
        num_nodes_per_chain: Optional[int] = None,
        fail_trials_on_premature_exit: bool = False,
        fail_trials_on_participant_performance_check: bool = False,
        propagate_failure: bool = True,
        num_repeat_trials: int = 0,
        wait_for_networks: bool = False,
        allow_revisiting_networks_in_across_chains: bool = False,
    ):
        assert chain_type in ["within", "across"]

        if (
            chain_type == "across"
            and num_trials_per_participant > num_chains_per_experiment
            and not allow_revisiting_networks_in_across_chains
        ):
            raise ValueError(
                "In across-chain experiments, <num_trials_per_participant> "
                "cannot exceed <num_chains_per_experiment> unless ``allow_revisiting_networks_in_across_chains`` "
                "is ``True``."
            )

        if chain_type == "within" and recruit_mode == "num_trials":
            raise ValueError(
                "In within-chain experiments the 'num_trials' recruit method is not available."
            )

        if (num_nodes_per_chain is not None) and (num_iterations_per_chain is not None):
            raise ValueError(
                "num_nodes_per_chain and num_iterations_per_chain cannot both be provided"
            )
        elif num_nodes_per_chain is not None:
            num_iterations_per_chain = num_nodes_per_chain - 1
            warnings.simplefilter("always", DeprecationWarning)
            warnings.warn(
                "num_nodes_per_chain is deprecated, use num_iterations_per_chain instead",
                DeprecationWarning,
            )
        elif num_iterations_per_chain is not None:
            pass
        elif (num_nodes_per_chain is None) and (num_iterations_per_chain is None):
            raise ValueError(
                "one of num_nodes_per_chain and num_iterations_per_chain must be provided"
            )

        self.node_class = node_class
        self.source_class = source_class
        self.trial_class = trial_class
        self.phase = phase
        self.chain_type = chain_type
        self.num_trials_per_participant = num_trials_per_participant
        self.num_chains_per_participant = num_chains_per_participant
        self.num_chains_per_experiment = num_chains_per_experiment
        self.num_iterations_per_chain = num_iterations_per_chain
        self.num_nodes_per_chain = num_iterations_per_chain + 1
        self.trials_per_node = trials_per_node
        self.balance_across_chains = balance_across_chains
        self.check_performance_at_end = check_performance_at_end
        self.check_performance_every_trial = check_performance_every_trial
        self.propagate_failure = propagate_failure
        self.allow_revisiting_networks_in_across_chains = (
            allow_revisiting_networks_in_across_chains
        )

        super().__init__(
            id_=id_,
            trial_class=trial_class,
            network_class=network_class,
            phase=phase,
            expected_num_trials=num_trials_per_participant + num_repeat_trials,
            check_performance_at_end=check_performance_at_end,
            check_performance_every_trial=check_performance_every_trial,
            fail_trials_on_premature_exit=fail_trials_on_premature_exit,
            fail_trials_on_participant_performance_check=fail_trials_on_participant_performance_check,
            propagate_failure=propagate_failure,
            recruit_mode=recruit_mode,
            target_num_participants=target_num_participants,
            num_repeat_trials=num_repeat_trials,
            wait_for_networks=wait_for_networks,
        )

    def init_participant(self, experiment, participant):
        super().init_participant(experiment, participant)
        self.init_participated_networks(participant)
        if self.chain_type == "within":
            self.create_networks_within(experiment, participant)

    @property
    def introduction(self):
        if self.chain_type == "within":
            return wait_while(
                negate(self.all_participant_networks_ready),
                expected_wait=5.0,
                log_message="Waiting for participant networks to be ready.",
            )
        return None

    def all_participant_networks_ready(self, participant):
        networks = self.network_class.query.filter_by(
            participant_id=participant.id, phase=self.phase, trial_maker_id=self.id
        ).all()
        return all([not x.awaiting_async_process for x in networks])

    @property
    def num_trials_still_required(self):
        assert self.chain_type == "across"
        return sum([network.num_trials_still_required for network in self.networks])

    #########################
    # Participated networks #
    #########################
    def init_participated_networks(self, participant):
        participant.var.set(self.with_namespace("participated_networks"), [])

    def get_participated_networks(self, participant):
        return participant.var.get(self.with_namespace("participated_networks"))

    def add_to_participated_networks(self, participant, network_id):
        networks = self.get_participated_networks(participant)
        networks.append(network_id)
        participant.var.set(self.with_namespace("participated_networks"), networks)

    def experiment_setup_routine(self, experiment):
        if self.num_networks == 0 and self.chain_type == "across":
            self.create_networks_across(experiment)

    def create_networks_within(self, experiment, participant):
        for i in range(self.num_chains_per_participant):
            self.create_network(experiment, participant, id_within_participant=i)

    def create_networks_across(self, experiment):
        for _ in range(self.num_chains_per_experiment):
            self.create_network(experiment)

    def create_network(self, experiment, participant=None, id_within_participant=None):
        network = self.network_class(
            trial_maker_id=self.id,
            source_class=self.source_class,
            phase=self.phase,
            experiment=experiment,
            chain_type=self.chain_type,
            trials_per_node=self.trials_per_node,
            target_num_nodes=self.num_nodes_per_chain,
            participant=participant,
            id_within_participant=id_within_participant,
        )
        db.session.add(network)
        db.session.commit()
        self._grow_network(network, participant, experiment)
        return network

    def find_networks(self, participant, experiment, ignore_async_processes=False):
        if (
            self.get_num_completed_trials_in_phase(participant)
            >= self.num_trials_per_participant
        ):
            return []

        networks = self.network_class.query.filter_by(
            trial_maker_id=self.id, phase=self.phase, full=False
        )

        if not ignore_async_processes:
            networks = networks.filter_by(awaiting_async_process=False)

        if self.chain_type == "within":
            networks = self.filter_by_participant_id(networks, participant)
        elif (
            self.chain_type == "across"
            and not self.allow_revisiting_networks_in_across_chains
        ):
            networks = self.exclude_participated(networks, participant)

        networks = networks.all()

        participant_group = participant.get_participant_group(self.id)
        networks = [n for n in networks if n.participant_group == participant_group]

        networks = self.custom_network_filter(
            candidates=networks, participant=participant
        )
        if not isinstance(networks, list):
            return TypeError("custom_network_filter must return a list of networks")

        random.shuffle(networks)

        if self.balance_across_chains:
            networks.sort(key=lambda network: network.num_completed_trials)

        return networks

    def custom_network_filter(self, candidates, participant):
        """
        Override this function to define a custom filter for choosing the participant's next network.

        Parameters
        ----------
        candidates:
            The current list of candidate networks as defined by the built-in chain procedure.

        participant:
            The current participant.

        Returns
        -------

        An updated list of candidate networks. The default implementation simply returns the original list.
        The experimenter might alter this function to remove certain networks from the list.
        """
        return candidates

    @staticmethod
    def filter_by_participant_id(networks, participant):
        return networks.filter_by(participant_id=participant.id)

    def exclude_participated(self, networks, participant):
        return networks.filter(
            not_(self.network_class.id.in_(self.get_participated_networks(participant)))
        )

    def grow_network(self, network, participant, experiment):
        # We set participant = None because of Dallinger's constraint of not allowing participants
        # to create nodes after they have finished working.
        participant = None
        head = network.head
        if head.ready_to_spawn:
            seed = head.create_seed(experiment, participant)
            node = self.node_class(
                seed,
                head.degree + 1,
                network,
                experiment,
                self.propagate_failure,
                participant,
            )
            db.session.add(node)
            network.add_node(node)
            db.session.commit()
            return True
        return False

    def find_node(self, network, participant, experiment):
        head = network.head
        if network.awaiting_async_process or (
            head.num_viable_trials >= self.trials_per_node
        ):
            return None
        return head

    def finalize_trial(self, answer, trial, experiment, participant):
        super().finalize_trial(answer, trial, experiment, participant)
        self.add_to_participated_networks(participant, trial.network_id)
