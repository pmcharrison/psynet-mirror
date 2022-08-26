import operator
import os
import random
from collections import Counter
from functools import reduce
from statistics import mean
from typing import List, Optional, Union

from dallinger import db
from dallinger.models import Vector
from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import relationship

from ..asset import CachedAsset
from ..timeline import NullElt, join
from ..utils import deep_copy, get_logger
from .main import (
    HasDefinition,
    NetworkTrialMaker,
    Trial,
    TrialNetwork,
    TrialNode,
    TrialSource,
)

logger = get_logger()


class SourceRegistry:
    csv_path = "source_registry.csv"

    def __init__(self, experiment):
        self.experiment = experiment
        self.timeline = experiment.timeline
        self.stimuli = {}
        self.compile_source_collections()
        # self.compile_stimuli()

    def __getitem__(self, item):
        try:
            return self.stimuli[item]
        except KeyError:
            raise KeyError(
                f"Can't find the source set '{item}' in the timeline. Are you sure you remembered to add it?"
            )

    # @property
    # def stimuli(self):
    #     return [
    #         s
    #         for _source_collection in self.source_collections.values()
    #         for s in _source_collection.stimuli
    #     ]

    def compile_source_collections(self):
        for elt in self.timeline.elts:
            if isinstance(elt, SourceCollection):
                id_ = elt.source_collection_id
                assert id_ is not None
                if id_ in self.stimuli and elt != self.stimuli[id_]:
                    raise RuntimeError(
                        f"Tried to register two non-identical source collections with the same ID: {id_}"
                    )
                self.stimuli[id_] = elt

    def prepare_for_deployment(self):
        self.create_networks()
        self.stage_assets()

    def create_networks(self):
        for source_collection in self.stimuli.values():
            source_collection.create_networks(self.experiment)
        null_network = GenericStimulusNetwork(self.experiment)
        db.session.add(null_network)
        db.session.commit()

    def stage_assets(self):
        for source_collection in self.stimuli.values():
            for source in source_collection.values():
                source.stage_assets(self.experiment)
        db.session.commit()


# TOOD - should this really be in the global namespace?


def filter_for_completed_trials(x):
    return x.filter_by(failed=False, complete=True, is_repeat_trial=False)


def query_all_completed_trials():
    return filter_for_completed_trials(StaticTrial.query)


class Stimulus(TrialNode, HasDefinition):
    """
    Defines a source for a static experiment.

    Parameters
    ----------

    definition
        A dictionary of parameters defining the source.

    participant_group
        The associated participant group.
        Defaults to a common participant group for all participants.

    block
        The associated block.
        Defaults to a single block for all trials.

    key
        Optional key that can be used to access the asset from the timeline.
        If left blank this will be populated automatically so as to be
        unique within a given source collection.

    Attributes
    ----------

    definition : dict
        A dictionary containing the parameter values for the source.

    participant_group : str
        The associated participant group.

    block : str
        The associated block.

    num_completed_trials : int
        The number of completed trials that this source has received,
        excluding failed trials.

    num_trials_still_required : int
        The number of trials still required for this source before the experiment
        can complete, if such a quota exists.
    """

    __extra_vars__ = {
        **TrialNode.__extra_vars__.copy(),
        **HasDefinition.__extra_vars__.copy(),
    }

    source_collection_id = Column(String, index=True)
    target_num_trials = Column(Integer)
    participant_group = Column(String)
    phase = Column(String)
    block = Column(String)
    key = Column(String, index=True)

    def __init__(
        self,
        definition: dict,
        *,
        participant_group="default",
        block="default",
        assets=None,
        key=None,
    ):
        # Note: We purposefully do not call super().__init__(), because this parent constructor
        # requires the prior existence of the node's parent network, which is impractical for us.
        assert isinstance(definition, dict)

        if assets is None:
            assets = {}

        #  TODO - remove phase from PsyNet, it is redundant when we have trial maker IDs
        phase = "experiment"

        self.definition = definition
        self.phase = phase
        self.participant_group = participant_group
        self.block = block
        self._staged_assets = assets
        self.key = key

    def stage_assets(self, experiment):
        source_id = self.id
        assert isinstance(source_id, int)

        self.assets = {**self.network.assets}

        for label, asset in self._staged_assets.items():
            if asset.label is None:
                asset.label = label

            if not asset.has_key:
                asset.set_key(
                    f"{self.source_collection_id}/stimuli/source_{source_id}__{asset.label}"
                )

            asset.parent = self

            asset.receive_source_definition(self.definition)
            asset.deposit()

            self.assets[label] = asset

        db.session.commit()
        self.assets = self._staged_assets
        db.session.commit()

    def add_to_network(self, network, source, target_num_trials, source_collection):
        assert network.phase == self.phase
        assert network.participant_group == self.participant_group
        assert network.block == self.block

        self.target_num_trials = target_num_trials
        self.network = network
        self.network_id = network.id

        v = Vector(origin=source, destination=self)
        db.session.add(v)

    @property
    def _query_completed_trials(self):
        return query_all_completed_trials().filter_by(source_id=self.id)

    @property
    def num_completed_trials(self):
        # TODO - revisit this logic
        return self._query_completed_trials.count()

    @property
    def num_trials_still_required(self):
        if self.target_num_trials is None:
            raise RuntimeError(
                "<num_trials_still_required> is not defined when <target_num_trials> is None."
            )
        return self.target_num_trials - self.num_completed_trials


UniqueConstraint(Stimulus.source_collection_id, Stimulus.key)

# __table_args__ = (
#     UniqueConstraint("source_collection_id", "key", name='_source_collection_id__key_uc'),
# )


class SourceCollection(NullElt):
    """
    Defines a source collection for a static experiment.
    This source collection is defined as a collection of
    :class:`~psynet.trial.static.Stimulus` objects.

    Parameters
    ----------

    stimuli: list
        A list of :class:`~psynet.trial.static.Stimulus` objects.
    """

    def __init__(
        self,
        id_: str,
        sources,
    ):
        assert isinstance(sources, list)
        assert isinstance(id_, str)

        self.sources = sources
        self.source_collection_id = id_
        self.phase = None
        self.trial_maker = None

        network_specs = set()
        blocks = set()
        participant_groups = set()
        self.num_sources = dict()

        for i, s in enumerate(sources):
            assert isinstance(s, Stimulus)

            s.source_collection_id = self.source_collection_id

            if s.key is None:
                s.key = f"source_{i}"

            network_specs.add((s.phase, s.participant_group, s.block))

            blocks.add(s.block)
            participant_groups.add(s.participant_group)

            # This logic could be refactored by defining a special dictionary class
            if s.participant_group not in self.num_sources:
                self.num_sources[s.participant_group] = dict()
            if s.block not in self.num_sources[s.participant_group]:
                self.num_sources[s.participant_group][s.block] = 0

            self.num_sources[s.participant_group][s.block] += 1

        self.network_specs = [
            NetworkSpec(
                phase=x[0], participant_group=x[1], block=x[2], source_collection=self
            )
            for x in network_specs
        ]

        self.blocks = sorted(list(blocks))
        self.participant_groups = sorted(list(participant_groups))

    def create_networks(self, experiment):
        if self.trial_maker is None:
            trial_maker_id = None
            target_num_trials_per_source = None
        else:
            trial_maker_id = self.trial_maker.id
            target_num_trials_per_source = self.trial_maker.target_num_trials_per_source

        for network_spec in self.network_specs:
            network = network_spec.create_network(
                trial_maker_id=trial_maker_id,
                experiment=experiment,
                target_num_trials_per_source=target_num_trials_per_source,
            )
            db.session.commit()
            network.populate(
                source_collection=self,
                target_num_trials_per_source=target_num_trials_per_source,
            )
            db.session.commit()

    def __getitem__(self, item):
        try:
            return Stimulus.query.filter_by(
                source_collection_id=self.source_collection_id, key=item
            ).one()
        except NoResultFound:
            return [source for source in self.sources if source.key == item][0]
        except IndexError:
            raise KeyError

    def items(self):
        from psynet.experiment import is_experiment_launched

        if is_experiment_launched():
            sources = Stimulus.query.filter_by(
                source_collection_id=self.source_collection_id,
            ).all()
        else:
            sources = self.sources

        return [(stim.key, stim) for stim in sources]

    def keys(self):
        return [stim[0] for stim in self.items()]

    def values(self):
        return [stim[1] for stim in self.items()]


class NetworkSpec:
    def __init__(self, phase, participant_group, block, source_collection):
        self.phase = phase
        self.participant_group = participant_group
        self.block = block
        self.source_collection = (
            source_collection  # note: this includes sources outside this network too!
        )

    def create_network(self, trial_maker_id, experiment, target_num_trials_per_source):
        network = StaticNetwork(
            trial_maker_id=trial_maker_id,
            phase=self.phase,
            participant_group=self.participant_group,
            block=self.block,
            experiment=experiment,
        )
        db.session.add(network)
        return network


class StaticTrial(Trial):
    """
    A Trial class for static experiments.

    The user must override the ``time_estimate`` class attribute,
    providing the estimated duration of the trial in seconds.
    This is used for predicting the participant's bonus payment
    and for constructing the progress bar.

    Attributes
    ----------

    time_estimate : numeric
        The estimated duration of the trial (including any feedback), in seconds.
        This should generally correspond to the (sum of the) ``time_estimate`` parameters in
        the page(s) generated by ``show_trial``, plus the ``time_estimate`` parameter in
        the page generated by ``show_feedback`` (if defined).
        This is used for predicting the participant's bonus payment
        and for constructing the progress bar.

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

    definition
        A dictionary of parameters defining the trial,
        inherited from the respective :class:`~psynet.trial.static.Stimulus` object.

    source
        The corresponding :class:`~psynet.trial.static.Stimulus`
        object.

    phase
        The phase of the experiment, e.g. ``"training"`` or ``"main"``.

    participant_group
        The associated participant group.

    block
        The block in which the trial is situated.
    """

    __extra_vars__ = Trial.__extra_vars__.copy()

    source_id = Column(Integer, ForeignKey("node.id"))
    source = relationship("Stimulus", foreign_keys=[source_id])

    phase = Column(String)
    participant_group = Column(String)
    block = Column(String)

    def __init__(self, experiment, node, *args, **kwargs):
        self.source = node
        self.source_id = node.id
        super().__init__(experiment, node, *args, **kwargs)
        self.phase = self.source.phase
        self.participant_group = self.source.participant_group
        self.block = self.source.block

    def generate_asset_key(self, asset):
        return f"{self.trial_maker_id}/block_{self.block}__source_{self.source_id}__trial_{self.id}__{asset.label}{asset.extension}"

    def show_trial(self, experiment, participant):
        raise NotImplementedError

    def make_definition(self, experiment, participant):
        for k, v in self.source.assets.items():
            self.assets[k] = v
        return deep_copy(self.source.definition)


class StaticTrialMaker(NetworkTrialMaker):
    """
    Administers a sequence of trials in a static experiment.
    The class is intended for use with the
    :class:`~psynet.trial.static.StaticTrial` helper class.
    which should be customised to show the relevant source
    for the experimental paradigm.
    The user must also define their source collection
    using the following built-in classes:

    * :class:`~psynet.trial.static.SourceCollection`;

    * :class:`~psynet.trial.static.Stimulus`;

    In particular, a :class:`~psynet.trial.static.SourceCollection`
    contains a list of :class:`~psynet.trial.static.Stimulus` objects.

    The user may also override the following methods, if desired:

    * :meth:`~psynet.trial.static.StaticTrialMaker.choose_block_order`;
      chooses the order of blocks in the experiment. By default the blocks
      are ordered randomly.

    * :meth:`~psynet.trial.static.StaticTrialMaker.choose_participant_group`;
      assigns the participant to a group. By default the participant is assigned
      to a random group.

    * :meth:`~psynet.trial.main.TrialMaker.on_complete`,
      run once the sequence of trials is complete.

    * :meth:`~psynet.trial.main.TrialMaker.performance_check`;
      checks the performance of the participant
      with a view to rejecting poor-performing participants.

    * :meth:`~psynet.trial.main.TrialMaker.compute_bonus`;
      computes the final performance bonus to assign to the participant.

    Further customisable options are available in the constructor's parameter list,
    documented below.

    Parameters
    ----------

    trial_class
        The class object for trials administered by this maker
        (should subclass :class:`~psynet.trial.static.StaticTrial`).

    phase
        Arbitrary label for this phase of the experiment, e.g.
        "practice", "train", "test".

    sources
        The source collection to be administered.

    recruit_mode
        Selects a recruitment criterion for determining whether to recruit
        another participant. The built-in criteria are ``"num_participants"``
        and ``"num_trials"``.

    target_num_participants
        Target number of participants to recruit for the experiment. All
        participants must successfully finish the experiment to count
        towards this quota. This target is only relevant if
        ``recruit_mode="num_participants"``.

    target_num_trials_per_source
        Target number of trials to recruit for each source in the experiment
        (as opposed to for each source version). This target is only relevant if
        ``recruit_mode="num_trials"``.

    max_trials_per_block
        Determines the maximum number of trials that a participant will be allowed to experience in each block,
        including failed trials. Note that this number does not include repeat trials.

    allow_repeated_sources
        Determines whether the participant can be administered the same source more than once.

    max_unique_sources_per_block
        Determines the maximum number of unique sources that a participant will be allowed to experience
        in each block. Once this quota is reached, the participant will be forced to repeat
        previously experienced sources.

    active_balancing_within_participants
        If ``True`` (default), active balancing within participants is enabled, meaning that
        source selection always favours the sources that have been presented fewest times
        to that participant so far.

    active_balancing_across_participants
        If ``True`` (default), active balancing across participants is enabled, meaning that
        source selection favours sources that have been presented fewest times to any participant
        in the experiment, excluding failed trials.
        This criterion defers to ``active_balancing_within_participants``;
        if both ``active_balancing_within_participants=True``
        and ``active_balancing_across_participants=True``,
        then the latter criterion is only used for tie breaking.

    check_performance_at_end
        If ``True``, the participant's performance
        is evaluated at the end of the series of trials.
        Defaults to ``False``.
        See :meth:`~psynet.trial.main.TrialMaker.performance_check`
        for implementing performance checks.

    check_performance_every_trial
        If ``True``, the participant's performance
        is evaluated after each trial.
        Defaults to ``False``.
        See :meth:`~psynet.trial.main.TrialMaker.performance_check`
        for implementing performance checks.

    fail_trials_on_premature_exit
        If ``True``, a participant's trials are marked as failed
        if they leave the experiment prematurely.
        Defaults to ``True``.

    fail_trials_on_participant_performance_check
        If ``True``, a participant's trials are marked as failed
        if the participant fails a performance check.
        Defaults to ``True``.

    num_repeat_trials
        Number of repeat trials to present to the participant. These trials
        are typically used to estimate the reliability of the participant's
        responses. Repeat trials are presented at the end of the trial maker,
        after all blocks have been completed.
        Defaults to 0.

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
        id_: str,
        trial_class,
        phase: str,
        sources: Union[List[Stimulus], SourceCollection],
        recruit_mode: Optional[str] = None,
        target_num_participants: Optional[int] = None,
        target_num_trials_per_source: Optional[int] = None,
        max_trials_per_block: Optional[int] = None,
        allow_repeated_sources: bool = False,
        max_unique_sources_per_block: Optional[int] = None,
        active_balancing_within_participants: bool = True,
        active_balancing_across_participants: bool = True,
        check_performance_at_end: bool = False,
        check_performance_every_trial: bool = False,
        fail_trials_on_premature_exit: bool = True,
        fail_trials_on_participant_performance_check: bool = True,
        num_repeat_trials: int = 0,
        source_collection=None,
    ):
        if source_collection is not None:
            raise ValueError(
                "The StaticTrialMaker 'source_collection' argument has been renamed to 'sources'."
            )

        if recruit_mode == "num_participants" and target_num_participants is None:
            raise ValueError(
                "<target_num_participants> cannot be None if recruit_mode == 'num_participants'."
            )
        if recruit_mode == "num_trials" and target_num_trials_per_source is None:
            raise ValueError(
                "<target_num_trials_per_source> cannot be None if recruit_mode == 'num_trials'."
            )
        if (target_num_participants is not None) and (
            target_num_trials_per_source is not None
        ):
            raise ValueError(
                "<target_num_participants> and <target_num_trials_per_source> cannot both be provided."
            )

        source_collection = (
            sources
            if isinstance(sources, SourceCollection)
            else SourceCollection(id_, sources)
        )
        source_collection.trial_maker = self

        self.source_collection = source_collection
        self.target_num_participants = target_num_participants
        self.target_num_trials_per_source = target_num_trials_per_source
        self.max_trials_per_block = max_trials_per_block
        self.allow_repeated_sources = allow_repeated_sources
        self.max_unique_sources_per_block = max_unique_sources_per_block
        self.active_balancing_within_participants = active_balancing_within_participants
        self.active_balancing_across_participants = active_balancing_across_participants

        expected_num_trials = self.estimate_num_trials(num_repeat_trials)

        super().__init__(
            id_=id_,
            trial_class=trial_class,
            network_class=StaticNetwork,
            phase=phase,
            expected_num_trials=expected_num_trials,
            check_performance_at_end=check_performance_at_end,
            check_performance_every_trial=check_performance_every_trial,
            fail_trials_on_premature_exit=fail_trials_on_premature_exit,
            fail_trials_on_participant_performance_check=fail_trials_on_participant_performance_check,
            propagate_failure=False,
            recruit_mode=recruit_mode,
            target_num_participants=target_num_participants,
            num_repeat_trials=num_repeat_trials,
            wait_for_networks=True,
        )

    def compile_elts(self):
        return join(self.source_collection, super().compile_elts())

    @property
    def num_trials_still_required(self):
        # Old version:
        # return sum([source.num_trials_still_required for source in self.sources])

        sources = self.sources
        source_actual_counts = self.get_trial_counts(sources)
        source_target_counts = [s.target_num_trials for s in sources]
        source_remaining_trials = [
            max(0, target - actual)
            for target, actual in zip(source_target_counts, source_actual_counts)
        ]

        return sum(source_remaining_trials)

    @property
    def sources(self):
        return [source for network in self.networks for source in network.sources]
        return reduce(operator.add, [n.sources for n in self.networks])

    def init_participant(self, experiment, participant):
        """
        Initializes the participant at the beginning of the sequence of trials.
        This includes choosing the block order, choosing the participant group
        (if relevant), and initialising a record of the participant's completed
        sources.
        If you override this, make sure you call ``super().init_particiant(...)``
        somewhere in your new method.

        Parameters
        ----------

        experiment
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.

        participant
            An instantiation of :class:`psynet.participant.Participant`,
            corresponding to the current participant.
        """
        super().init_participant(experiment, participant)
        self.init_block_order(experiment, participant)
        self.init_completed_sources_in_phase(participant)

    def estimate_num_trials_in_block(self, num_sources_in_block):
        if self.allow_repeated_sources:
            return self.max_trials_per_block
        else:
            if self.max_trials_per_block is None:
                return num_sources_in_block
            else:
                return min(num_sources_in_block, self.max_trials_per_block)

    def estimate_num_trials(self, num_repeat_trials):
        return (
            mean(
                [
                    sum(
                        [
                            self.estimate_num_trials_in_block(num_sources_in_block)
                            for num_sources_in_block in num_sources_by_block.values()
                        ]
                    )
                    for participant_group, num_sources_by_block in self.source_collection.num_sources.items()
                ]
            )
            + num_repeat_trials
        )

    def finalize_trial(self, answer, trial, experiment, participant):
        """
        This calls the base class's ``finalize_trial`` method,
        then increments the number of completed sources in the phase and the block.
        """
        super().finalize_trial(answer, trial, experiment, participant)
        self.increment_completed_sources_in_phase_and_block(
            participant, trial.block, trial.source_id
        )
        # trial.source.num_completed_trials += 1

    def init_block_order(self, experiment, participant):
        self.set_block_order(
            participant,
            self.choose_block_order(experiment=experiment, participant=participant),
        )

    @property
    def block_order_var_id(self):
        return self.with_namespace("block_order")

    def set_block_order(self, participant, block_order):
        participant.var.new(self.block_order_var_id, block_order)

    def get_block_order(self, participant):
        return participant.var.get(self.with_namespace("block_order"))

    def init_completed_sources_in_phase(self, participant):
        participant.var.set(
            self.with_namespace("completed_sources_in_phase"),
            {block: Counter() for block in self.source_collection.blocks},
        )

    def get_completed_sources_in_phase(self, participant):
        all_counters = participant.var.get(
            self.with_namespace("completed_sources_in_phase")
        )

        def load_counter(input):
            return Counter({int(key): value for key, value in input.items()})

        return {block: load_counter(counter) for block, counter in all_counters.items()}

    def get_completed_sources_in_phase_and_block(self, participant, block):
        all_counters = self.get_completed_sources_in_phase(participant)
        return all_counters[block]

    def increment_completed_sources_in_phase_and_block(
        self, participant, block, source_id
    ):
        all_counters = self.get_completed_sources_in_phase(participant)
        all_counters[block][source_id] += 1
        participant.var.set(
            self.with_namespace("completed_sources_in_phase"), all_counters
        )

    def on_complete(self, experiment, participant):
        pass

    def choose_block_order(self, experiment, participant):
        # pylint: disable=unused-argument
        """
        Determines the order of blocks for the current participant.
        By default this function shuffles the blocks randomly for each participant.
        The user is invited to override this function for alternative behaviour.

        Parameters
        ----------

        experiment
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.

        participant
            An instantiation of :class:`psynet.participant.Participant`,
            corresponding to the current participant.

        Returns
        -------

        list
            A list of blocks in order of presentation,
            where each block is identified by a string label.
        """
        blocks = self.source_collection.blocks
        random.shuffle(blocks)
        return blocks

    def choose_participant_group(self, experiment, participant):
        # pylint: disable=unused-argument
        """
        Determines the participant group assigned to the current participant
        (ignored if the participant already has been assigned to a participant group for that trial maker
        using e.g. participant.set_participant_group).
        By default this function randomly chooses from the available participant groups.
        The user is invited to override this function for alternative behaviour.

        Parameters
        ----------

        experiment
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.

        participant
            An instantiation of :class:`psynet.participant.Participant`,
            corresponding to the current participant.

        Returns
        -------

        A string label identifying the selected participant group.
        """
        participant_groups = self.source_collection.participant_groups
        return random.choice(participant_groups)

    def find_networks(self, participant, experiment):
        # pylint: disable=protected-access
        block_order = participant.var.get(self.with_namespace("block_order"))
        networks = StaticNetwork.query.filter_by(
            trial_maker_id=self.id,
            participant_group=participant.get_participant_group(self.id),
            # We used to filter by phase but now we are deprecating phase,
            # as all necessary information is provided by the trialmaker.
            #
            # phase=self.phase,
        ).filter(StaticNetwork.block.in_(block_order))
        networks = networks.all()
        networks.sort(key=lambda network: block_order.index(network.block))
        return networks

    def grow_network(self, network, experiment):
        """
        Does nothing, because networks never get expanded in a static experiment.
        """
        return False

    def find_node(self, network, participant, experiment):
        return self.find_source(network, participant, experiment)

    def count_completed_trials_in_network(self, network, participant):
        return self.trial_class.query.filter_by(
            network_id=network.id,
            participant_id=participant.id,
            complete=True,
            is_repeat_trial=False,
        ).count()

    def find_source(self, network, participant, experiment):
        # pylint: disable=unused-argument,protected-access
        if (
            self.max_trials_per_block is not None
            and self.count_completed_trials_in_network(network, participant)
            >= self.max_trials_per_block
        ):
            return None
        completed_sources = self.get_completed_sources_in_phase_and_block(
            participant, block=network.block
        )
        allow_new_source = self.check_allow_new_source(completed_sources)
        candidates = Stimulus.query.filter_by(
            network_id=network.id
        ).all()  # networks are guaranteed to be from the correct phase
        if not self.allow_repeated_sources:
            candidates = self.filter_out_repeated_sources(candidates, completed_sources)
        if not allow_new_source:
            candidates = self.filter_out_new_sources(candidates, completed_sources)

        candidates = self.custom_source_filter(
            candidates=candidates, participant=participant
        )
        if not isinstance(candidates, list):
            return ValueError("custom_source_filter must return a list of sources")

        if self.active_balancing_within_participants:
            candidates = self.balance_within_participants(candidates, completed_sources)
        if self.active_balancing_across_participants:
            candidates = self.balance_across_participants(candidates)
        if len(candidates) == 0:
            return None
        return random.choice(candidates)

    def check_allow_new_source(self, completed_sources):
        if self.max_unique_sources_per_block is None:
            return True
        num_unique_completed_sources = len(completed_sources)
        return num_unique_completed_sources < self.max_unique_sources_per_block

    def custom_source_filter(self, candidates, participant):
        """
        Override this function to define a custom filter for choosing the participant's next source.

        Parameters
        ----------
        candidates:
            The current list of candidate sources as defined by the built-in static experiment procedure.

        participant:
            The current participant.

        Returns
        -------

        An updated list of candidate sources. The default implementation simply returns the original list.
        The experimenter might alter this function to remove certain sources from the list.
        """
        return candidates

    @staticmethod
    def filter_out_repeated_sources(candidates, completed_sources):
        return [x for x in candidates if x.id not in completed_sources.keys()]

    @staticmethod
    def filter_out_new_sources(candidates, completed_sources):
        return [x for x in candidates if x.id in completed_sources.keys()]

    @staticmethod
    def balance_within_participants(candidates, completed_sources):
        candidate_counts_within = [
            completed_sources[candidate.id] for candidate in candidates
        ]
        min_count_within = (
            0 if len(candidate_counts_within) == 0 else min(candidate_counts_within)
        )
        return [
            candidate
            for candidate, candidate_count_within in zip(
                candidates, candidate_counts_within
            )
            if candidate_count_within == min_count_within
        ]

    def get_trial_counts(self, sources):
        n_trials_all_sources = filter_for_completed_trials(
            db.session.query(
                StaticTrial.source_id, func.count(StaticTrial.id)
            ).group_by(StaticTrial.source_id)
        ).all()
        n_trials_all_sources = {x[0]: x[1] for x in n_trials_all_sources}

        def get_count(source):
            try:
                return n_trials_all_sources[source.id]
            except KeyError:
                return 0

        return [get_count(stim) for stim in sources]

    def balance_across_participants(self, candidates):
        candidate_counts_across = self.get_trial_counts(candidates)

        min_count_across = (
            0 if len(candidate_counts_across) == 0 else min(candidate_counts_across)
        )
        return [
            candidate
            for candidate, candidate_count_across in zip(
                candidates, candidate_counts_across
            )
            if candidate_count_across == min_count_across
        ]


class StaticNetwork(TrialNetwork):
    """
    A :class:`~psynet.trial.main.TrialNetwork` class for static experiments.
    The user should not have to engage with this class directly,
    except through the network visualisation tool and through
    analysing the resulting data.
    The networks are organised as follows:

    1. At the top level of the hierarchy, different networks correspond to different
       combinations of participant group and block.
       If the same experiment contains many
       :class:`~psynet.trial.static.StaticTrialMaker` objects
       with different associated :class:`~psynet.trial.static.StaticTrial`
       classes,
       then networks will also be differentiated by the names of these
       :class:`~psynet.trial.static.StaticTrial` classes.

    2. Within a given network, the first level of the hierarchy is the
       :class:`~psynet.trial.static.Stimulus` class.
       These are generated directly from :class:`~psynet.trial.static.Stimulus` instances.

    4. Nested within :class:`~psynet.trial.static.Stimulus` objects
       are :class:`~psynet.trial.static.StaticTrial` objects.

    Attributes
    ----------

    target_num_trials : int or None
        Indicates the target number of trials for that network.

    awaiting_async_process : bool
        Whether the network is currently closed and waiting for an asynchronous process to complete.
        This should always be ``False`` for static experiments.

    earliest_async_process_start_time : Optional[datetime]
        Time at which the earliest pending async process was called.

    participant_group : bool
        The network's associated participant group.

    block : str
        The network's associated block.

    num_nodes : int
        Returns the number of non-failed nodes in the network.

    num_completed_trials : int
        Returns the number of completed and non-failed trials in the network,
        irrespective of asynchronous processes,
        but excluding end-of-phase repeat trials.

    sources : list
        Returns the sources associated with the network.

    num_sources : int
        Returns the number of sources associated with the network.

    var : :class:`~psynet.field.VarStore`
        A repository for arbitrary variables; see :class:`~psynet.field.VarStore` for details.
    """

    # pylint: disable=abstract-method

    __extra_vars__ = TrialNetwork.__extra_vars__.copy()

    block = Column(String)

    def __init__(
        self,
        *,
        trial_maker_id,
        phase,
        participant_group,
        block,
        experiment,
    ):
        self.participant_group = participant_group
        self.block = block
        super().__init__(trial_maker_id, phase, experiment)

    def populate(self, source_collection, target_num_trials_per_source):
        logger.info("Creating source network (id = %i)...", self.id)
        source = TrialSource(network=self)
        db.session.add(source)
        sources = [
            x
            for x in source_collection.sources
            if x.phase == self.phase
            and x.participant_group == self.participant_group
            and x.block == self.block
        ]
        N = len(sources)
        n = 0
        for i, source in enumerate(sources):
            source.add_to_network(
                network=self,
                source=source,
                target_num_trials=target_num_trials_per_source,
                source_collection=source_collection,
            )
            n = i + 1
            if n % 100 == 0:
                logger.info("Populated network %i with %i/%i sources...", self.id, n, N)
                db.session.commit()
        logger.info("Finished populating network %i with %i/%i sources.", self.id, n, N)
        db.session.commit()

    @property
    def source_query(self):
        return Stimulus.query.filter_by(network_id=self.id)

    @property
    def sources(self):
        return self.source_query.all()

    @property
    def num_sources(self):
        return self.source_query.count()


class GenericStimulusNetwork(StaticNetwork):
    def __init__(self, experiment):
        super().__init__(
            trial_maker_id=None,
            phase="experiment",
            participant_group="default",
            block="default",
            experiment=experiment,
        )


class SourceCollectionFromDir(SourceCollection):
    def __init__(
        self, id_: str, input_dir: str, media_ext: str, asset_label: str = "prompt"
    ):
        sources = []
        participant_groups = [
            (f.name, f.path) for f in os.scandir(input_dir) if f.is_dir()
        ]
        for participant_group, group_path in participant_groups:
            blocks = [(f.name, f.path) for f in os.scandir(group_path) if f.is_dir()]
            for block, block_path in blocks:
                media_files = [
                    (f.name, f.path)
                    for f in os.scandir(block_path)
                    if f.is_file() and f.path.endswith(media_ext)
                ]
                for media_name, media_path in media_files:
                    sources.append(
                        Stimulus(
                            definition={
                                "name": media_name,
                            },
                            assets={
                                asset_label: CachedAsset(
                                    input_path=media_path,
                                    extension=media_ext,
                                )
                            },
                            participant_group=participant_group,
                            block=block,
                        )
                    )
        return super().__init__(id_, sources)
