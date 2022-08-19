import operator
import os
import pickle
import random
from collections import Counter
from functools import reduce
from pathlib import Path
from statistics import mean
from typing import List, Optional, Union

from dallinger import db
from dallinger.models import Vector
from sqlalchemy import Column, Integer, String, UniqueConstraint, func
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


class StimulusRegistry:
    csv_path = "stimulus_registry.csv"

    def __init__(self, experiment):
        self.experiment = experiment
        self.timeline = experiment.timeline
        self.stimuli = {}
        self.compile_stimulus_sets()
        # self.compile_stimuli()

    def __getitem__(self, item):
        try:
            return self.stimuli[item]
        except KeyError:
            raise KeyError(
                f"Can't find the stimulus set '{item}' in the timeline. Are you sure you remembered to add it?"
            )

    # @property
    # def stimuli(self):
    #     return [
    #         s
    #         for _stimulus_set in self.stimulus_sets.values()
    #         for s in _stimulus_set.stimuli
    #     ]

    def compile_stimulus_sets(self):
        for elt in self.timeline.elts:
            if isinstance(elt, StimulusSet):
                id_ = elt.stimulus_set_id
                assert id_ is not None
                if id_ in self.stimuli and elt != self.stimuli[id_]:
                    raise RuntimeError(
                        f"Tried to register two non-identical stimulus sets with the same ID: {id_}"
                    )
                self.stimuli[id_] = elt

    def prepare_for_deployment(self):
        self.create_networks()
        self.stage_assets()

    def create_networks(self):
        for stimulus_set in self.stimuli.values():
            stimulus_set.create_networks(self.experiment)
        null_network = StaticNetwork(
            trial_maker_id=None,
            phase="experiment",
            participant_group="default",
            block="default",
            experiment=self.experiment,
        )
        db.session.add(null_network)
        db.session.commit()

    def stage_assets(self):
        for stimulus_set in self.stimuli.values():
            for stimulus in stimulus_set.values():
                stimulus.stage_assets(self.experiment)
        db.session.commit()


# TOOD - should this really be in the global namespace?


def filter_for_completed_trials(x):
    return x.filter_by(failed=False, complete=True, is_repeat_trial=False)


def query_all_completed_trials():
    return filter_for_completed_trials(StaticTrial.query)


class Stimulus(TrialNode, HasDefinition):
    """
    Defines a stimulus for a static experiment.

    Parameters
    ----------

    definition
        A dictionary of parameters defining the stimulus.

    participant_group
        The associated participant group.
        Defaults to a common participant group for all participants.

    block
        The associated block.
        Defaults to a single block for all trials.

    key
        Optional key that can be used to access the asset from the timeline.
        If left blank this will be populated automatically so as to be
        unique within a given stimulus set.

    Attributes
    ----------

    definition : dict
        A dictionary containing the parameter values for the stimulus.

    participant_group : str
        The associated participant group.

    block : str
        The associated block.

    num_completed_trials : int
        The number of completed trials that this stimulus has received,
        excluding failed trials.

    num_trials_still_required : int
        The number of trials still required for this stimulus before the experiment
        can complete, if such a quota exists.
    """

    __extra_vars__ = {
        **TrialNode.__extra_vars__.copy(),
        **HasDefinition.__extra_vars__.copy(),
    }

    stimulus_set_id = Column(String, index=True)
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
        stimulus_id = self.id
        assert isinstance(stimulus_id, int)

        self.assets = {**self.network.assets}

        for label, asset in self._staged_assets.items():
            if asset.label is None:
                asset.label = label

            if not asset.has_key:
                asset.key = f"{self.stimulus_set_id}/stimulus_{stimulus_id}__{asset.label}{asset.extension}"

            asset.parent = self

            # asset.node = self
            # asset.node_id = self.id
            #
            # asset.network = self.network
            # asset.network_id = self.network_id

            asset.receive_stimulus_definition(self.definition)
            asset.deposit()
            # experiment.assets.stage(asset)
            # db.session.add(asset)

            self.assets[label] = asset

        db.session.commit()
        self.assets = self._staged_assets
        db.session.commit()

    def add_to_network(self, network, source, target_num_trials, stimulus_set):
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
        return query_all_completed_trials().filter_by(stimulus_id=self.id)

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


UniqueConstraint(Stimulus.stimulus_set_id, Stimulus.key)

# __table_args__ = (
#     UniqueConstraint("stimulus_set_id", "key", name='_stimulus_set_id__key_uc'),
# )


class StimulusSet(NullElt):
    """
    Defines a stimulus set for a static experiment.
    This stimulus set is defined as a collection of
    :class:`~psynet.trial.static.Stimulus` objects.

    Parameters
    ----------

    stimuli: list
        A list of :class:`~psynet.trial.static.Stimulus` objects.
    """

    def __init__(
        self,
        id_: str,
        stimuli,
    ):
        assert isinstance(stimuli, list)
        assert isinstance(id_, str)

        self.stimuli = stimuli
        self.stimulus_set_id = id_
        self.phase = None
        self.trial_maker = None

        network_specs = set()
        blocks = set()
        participant_groups = set()
        self.num_stimuli = dict()

        for i, s in enumerate(stimuli):
            assert isinstance(s, Stimulus)

            s.stimulus_set_id = self.stimulus_set_id

            if s.key is None:
                s.key = f"stimulus_{i}"

            network_specs.add((s.phase, s.participant_group, s.block))

            blocks.add(s.block)
            participant_groups.add(s.participant_group)

            # This logic could be refactored by defining a special dictionary class
            if s.participant_group not in self.num_stimuli:
                self.num_stimuli[s.participant_group] = dict()
            if s.block not in self.num_stimuli[s.participant_group]:
                self.num_stimuli[s.participant_group][s.block] = 0

            self.num_stimuli[s.participant_group][s.block] += 1

        self.network_specs = [
            NetworkSpec(
                phase=x[0], participant_group=x[1], block=x[2], stimulus_set=self
            )
            for x in network_specs
        ]

        self.blocks = sorted(list(blocks))
        self.participant_groups = sorted(list(participant_groups))

    def create_networks(self, experiment):
        if self.trial_maker is None:
            trial_maker_id = None
            target_num_trials_per_stimulus = None
        else:
            trial_maker_id = self.trial_maker.id
            target_num_trials_per_stimulus = (
                self.trial_maker.target_num_trials_per_stimulus
            )

        for network_spec in self.network_specs:
            network = network_spec.create_network(
                trial_maker_id=trial_maker_id,
                experiment=experiment,
                target_num_trials_per_stimulus=target_num_trials_per_stimulus,
            )
            db.session.commit()
            network.populate(
                stimulus_set=self,
                target_num_trials_per_stimulus=target_num_trials_per_stimulus,
            )
            db.session.commit()

    def __getitem__(self, item):
        try:
            return Stimulus.query.filter_by(
                stimulus_set_id=self.stimulus_set_id, key=item
            ).one()
        except NoResultFound:
            return [stimulus for stimulus in self.stimuli if stimulus.key == item][0]
        except IndexError:
            raise KeyError

    def items(self):
        from psynet.experiment import is_experiment_launched

        if is_experiment_launched():
            stimuli = Stimulus.query.filter_by(
                stimulus_set_id=self.stimulus_set_id,
            ).all()
        else:
            stimuli = self.stimuli

        return [(stim.key, stim) for stim in stimuli]

    def keys(self):
        return [stim[0] for stim in self.items()]

    def values(self):
        return [stim[1] for stim in self.items()]


class VirtualStimulusSet:
    # TODO - revisit, this probably won't work any more
    def __init__(self, id_: str, version: str, construct):
        self.id = id_
        self.version = version
        self.construct = construct

        if not self.cache_exists:
            self.build_cache()

        # if len(sys.argv) > 1 and sys.argv[1] == "prepare":
        #     self.prepare_media()

    def build_cache(self):
        # logger.info("(%s) Building stimulus set cache...", self.id)
        stimulus_set = self.construct()
        self.save_to_cache(stimulus_set)

    @property
    def cache_dir(self):
        return os.path.join("_stimulus_sets", self.id)

    @property
    def cache_path(self):
        return os.path.join(self.cache_dir, f"{self.version}.pickle")

    @property
    def cache_exists(self):
        return os.path.isfile(self.cache_path)

    def save_to_cache(self, stimulus_set):
        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, "wb") as f:
            pickle.dump(stimulus_set, f)

    def load(self):
        with open(self.cache_path, "rb") as f:
            return pickle.load(f)


class NetworkSpec:
    def __init__(self, phase, participant_group, block, stimulus_set):
        self.phase = phase
        self.participant_group = participant_group
        self.block = block
        self.stimulus_set = (
            stimulus_set  # note: this includes stimuli outside this network too!
        )

    def create_network(
        self, trial_maker_id, experiment, target_num_trials_per_stimulus
    ):
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

    stimulus
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

    stimulus_id = Column(Integer)
    stimulus = relationship(Stimulus)
    phase = Column(String)
    participant_group = Column(String)
    block = Column(String)

    def __init__(self, experiment, node, *args, **kwargs):
        self.stimulus = node
        self.stimulus_id = node.id
        super().__init__(experiment, node, *args, **kwargs)
        self.phase = self.stimulus.phase
        self.participant_group = self.stimulus.participant_group
        self.block = self.stimulus.block

    def generate_asset_key(self, asset):
        return f"{self.trial_maker_id}/block_{self.block}__stimulus_{self.stimulus_id}__trial_{self.id}__{asset.label}{asset.extension}"

    def show_trial(self, experiment, participant):
        raise NotImplementedError

    def make_definition(self, experiment, participant):
        for k, v in self.stimulus.assets.items():
            self.assets[k] = v
        return deep_copy(self.stimulus.definition)

    def summarize(self):
        return {
            "participant_group": self.participant_group,
            "phase": self.phase,
            "block": self.block,
            "definition": self.definition,
            "media_url": self.media_url,
            "trial_id": self.id,
            "stimulus_id": self.stimulus.id,
            "stimulus_version_id": self.stimulus_version.id,
        }


class StaticTrialMaker(NetworkTrialMaker):
    """
    Administers a sequence of trials in a static experiment.
    The class is intended for use with the
    :class:`~psynet.trial.static.StaticTrial` helper class.
    which should be customised to show the relevant stimulus
    for the experimental paradigm.
    The user must also define their stimulus set
    using the following built-in classes:

    * :class:`~psynet.trial.static.StimulusSet`;

    * :class:`~psynet.trial.static.Stimulus`;

    In particular, a :class:`~psynet.trial.static.StimulusSet`
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

    stimuli
        The stimulus set to be administered.

    recruit_mode
        Selects a recruitment criterion for determining whether to recruit
        another participant. The built-in criteria are ``"num_participants"``
        and ``"num_trials"``.

    target_num_participants
        Target number of participants to recruit for the experiment. All
        participants must successfully finish the experiment to count
        towards this quota. This target is only relevant if
        ``recruit_mode="num_participants"``.

    target_num_trials_per_stimulus
        Target number of trials to recruit for each stimulus in the experiment
        (as opposed to for each stimulus version). This target is only relevant if
        ``recruit_mode="num_trials"``.

    max_trials_per_block
        Determines the maximum number of trials that a participant will be allowed to experience in each block,
        including failed trials. Note that this number does not include repeat trials.

    allow_repeated_stimuli
        Determines whether the participant can be administered the same stimulus more than once.

    max_unique_stimuli_per_block
        Determines the maximum number of unique stimuli that a participant will be allowed to experience
        in each block. Once this quota is reached, the participant will be forced to repeat
        previously experienced stimuli.

    active_balancing_within_participants
        If ``True`` (default), active balancing within participants is enabled, meaning that
        stimulus selection always favours the stimuli that have been presented fewest times
        to that participant so far.

    active_balancing_across_participants
        If ``True`` (default), active balancing across participants is enabled, meaning that
        stimulus selection favours stimuli that have been presented fewest times to any participant
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
        stimuli: Union[List[Stimulus], StimulusSet],
        recruit_mode: Optional[str] = None,
        target_num_participants: Optional[int] = None,
        target_num_trials_per_stimulus: Optional[int] = None,
        max_trials_per_block: Optional[int] = None,
        allow_repeated_stimuli: bool = False,
        max_unique_stimuli_per_block: Optional[int] = None,
        active_balancing_within_participants: bool = True,
        active_balancing_across_participants: bool = True,
        check_performance_at_end: bool = False,
        check_performance_every_trial: bool = False,
        fail_trials_on_premature_exit: bool = True,
        fail_trials_on_participant_performance_check: bool = True,
        num_repeat_trials: int = 0,
        stimulus_set=None,
    ):
        if stimulus_set is not None:
            raise ValueError(
                "The StaticTrialMaker 'stimulus_set' argument has been renamed to 'stimuli'."
            )

        if recruit_mode == "num_participants" and target_num_participants is None:
            raise ValueError(
                "<target_num_participants> cannot be None if recruit_mode == 'num_participants'."
            )
        if recruit_mode == "num_trials" and target_num_trials_per_stimulus is None:
            raise ValueError(
                "<target_num_trials_per_stimulus> cannot be None if recruit_mode == 'num_trials'."
            )
        if (target_num_participants is not None) and (
            target_num_trials_per_stimulus is not None
        ):
            raise ValueError(
                "<target_num_participants> and <target_num_trials_per_stimulus> cannot both be provided."
            )

        stimulus_set = (
            stimuli if isinstance(stimuli, StimulusSet) else StimulusSet(id_, stimuli)
        )
        stimulus_set.trial_maker = self

        self.stimulus_set = stimulus_set
        self.target_num_participants = target_num_participants
        self.target_num_trials_per_stimulus = target_num_trials_per_stimulus
        self.max_trials_per_block = max_trials_per_block
        self.allow_repeated_stimuli = allow_repeated_stimuli
        self.max_unique_stimuli_per_block = max_unique_stimuli_per_block
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
        return join(self.stimulus_set, super().compile_elts())

    @property
    def num_trials_still_required(self):
        # Old version:
        # return sum([stimulus.num_trials_still_required for stimulus in self.stimuli])

        stimuli = self.stimuli
        stimulus_actual_counts = self.get_trial_counts(stimuli)
        stimulus_target_counts = [s.target_num_trials for s in stimuli]
        stimulus_remaining_trials = [
            max(0, target - actual)
            for target, actual in zip(stimulus_target_counts, stimulus_actual_counts)
        ]

        return sum(stimulus_remaining_trials)

    @property
    def stimuli(self):
        return [stimulus for network in self.networks for stimulus in network.stimuli]
        return reduce(operator.add, [n.stimuli for n in self.networks])

    def init_participant(self, experiment, participant):
        """
        Initializes the participant at the beginning of the sequence of trials.
        This includes choosing the block order, choosing the participant group
        (if relevant), and initialising a record of the participant's completed
        stimuli.
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
        self.init_completed_stimuli_in_phase(participant)

    def estimate_num_trials_in_block(self, num_stimuli_in_block):
        if self.allow_repeated_stimuli:
            return self.max_trials_per_block
        else:
            if self.max_trials_per_block is None:
                return num_stimuli_in_block
            else:
                return min(num_stimuli_in_block, self.max_trials_per_block)

    def estimate_num_trials(self, num_repeat_trials):
        return (
            mean(
                [
                    sum(
                        [
                            self.estimate_num_trials_in_block(num_stimuli_in_block)
                            for num_stimuli_in_block in num_stimuli_by_block.values()
                        ]
                    )
                    for participant_group, num_stimuli_by_block in self.stimulus_set.num_stimuli.items()
                ]
            )
            + num_repeat_trials
        )

    def finalize_trial(self, answer, trial, experiment, participant):
        """
        This calls the base class's ``finalize_trial`` method,
        then increments the number of completed stimuli in the phase and the block.
        """
        super().finalize_trial(answer, trial, experiment, participant)
        self.increment_completed_stimuli_in_phase_and_block(
            participant, trial.block, trial.stimulus_id
        )
        # trial.stimulus.num_completed_trials += 1

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

    def init_completed_stimuli_in_phase(self, participant):
        participant.var.set(
            self.with_namespace("completed_stimuli_in_phase"),
            {block: Counter() for block in self.stimulus_set.blocks},
        )

    def get_completed_stimuli_in_phase(self, participant):
        all_counters = participant.var.get(
            self.with_namespace("completed_stimuli_in_phase")
        )

        def load_counter(input):
            return Counter({int(key): value for key, value in input.items()})

        return {block: load_counter(counter) for block, counter in all_counters.items()}

    def get_completed_stimuli_in_phase_and_block(self, participant, block):
        all_counters = self.get_completed_stimuli_in_phase(participant)
        return all_counters[block]

    def increment_completed_stimuli_in_phase_and_block(
        self, participant, block, stimulus_id
    ):
        all_counters = self.get_completed_stimuli_in_phase(participant)
        all_counters[block][stimulus_id] += 1
        participant.var.set(
            self.with_namespace("completed_stimuli_in_phase"), all_counters
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
        blocks = self.stimulus_set.blocks
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
        participant_groups = self.stimulus_set.participant_groups
        return random.choice(participant_groups)

    def find_networks(self, participant, experiment, ignore_async_processes=False):
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
        if not ignore_async_processes:
            networks = networks.filter_by(awaiting_async_process=False)
        networks = networks.all()
        networks.sort(key=lambda network: block_order.index(network.block))
        return networks

    def grow_network(self, network, participant, experiment):
        """
        Does nothing, because networks never get expanded in a static experiment.
        """
        return False

    def find_node(self, network, participant, experiment):
        return self.find_stimulus(network, participant, experiment)

    def count_completed_trials_in_network(self, network, participant):
        return self.trial_class.query.filter_by(
            network_id=network.id,
            participant_id=participant.id,
            complete=True,
            is_repeat_trial=False,
        ).count()

    def find_stimulus(self, network, participant, experiment):
        # pylint: disable=unused-argument,protected-access
        if (
            self.max_trials_per_block is not None
            and self.count_completed_trials_in_network(network, participant)
            >= self.max_trials_per_block
        ):
            return None
        completed_stimuli = self.get_completed_stimuli_in_phase_and_block(
            participant, block=network.block
        )
        allow_new_stimulus = self.check_allow_new_stimulus(completed_stimuli)
        candidates = Stimulus.query.filter_by(
            network_id=network.id
        ).all()  # networks are guaranteed to be from the correct phase
        if not self.allow_repeated_stimuli:
            candidates = self.filter_out_repeated_stimuli(candidates, completed_stimuli)
        if not allow_new_stimulus:
            candidates = self.filter_out_new_stimuli(candidates, completed_stimuli)

        candidates = self.custom_stimulus_filter(
            candidates=candidates, participant=participant
        )
        if not isinstance(candidates, list):
            return ValueError("custom_stimulus_filter must return a list of stimuli")

        if self.active_balancing_within_participants:
            candidates = self.balance_within_participants(candidates, completed_stimuli)
        if self.active_balancing_across_participants:
            candidates = self.balance_across_participants(candidates)
        if len(candidates) == 0:
            return None
        return random.choice(candidates)

    def check_allow_new_stimulus(self, completed_stimuli):
        if self.max_unique_stimuli_per_block is None:
            return True
        num_unique_completed_stimuli = len(completed_stimuli)
        return num_unique_completed_stimuli < self.max_unique_stimuli_per_block

    def custom_stimulus_filter(self, candidates, participant):
        """
        Override this function to define a custom filter for choosing the participant's next stimulus.

        Parameters
        ----------
        candidates:
            The current list of candidate stimuli as defined by the built-in static experiment procedure.

        participant:
            The current participant.

        Returns
        -------

        An updated list of candidate stimuli. The default implementation simply returns the original list.
        The experimenter might alter this function to remove certain stimuli from the list.
        """
        return candidates

    @staticmethod
    def filter_out_repeated_stimuli(candidates, completed_stimuli):
        return [x for x in candidates if x.id not in completed_stimuli.keys()]

    @staticmethod
    def filter_out_new_stimuli(candidates, completed_stimuli):
        return [x for x in candidates if x.id in completed_stimuli.keys()]

    @staticmethod
    def balance_within_participants(candidates, completed_stimuli):
        candidate_counts_within = [
            completed_stimuli[candidate.id] for candidate in candidates
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

    def get_trial_counts(self, stimuli):
        n_trials_all_stimuli = filter_for_completed_trials(
            db.session.query(
                StaticTrial.stimulus_id, func.count(StaticTrial.id)
            ).group_by(StaticTrial.stimulus_id)
        ).all()
        n_trials_all_stimuli = {x[0]: x[1] for x in n_trials_all_stimuli}

        def get_count(stimulus):
            try:
                return n_trials_all_stimuli[stimulus.id]
            except KeyError:
                return 0

        return [get_count(stim) for stim in stimuli]

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

    stimuli : list
        Returns the stimuli associated with the network.

    num_stimuli : int
        Returns the number of stimuli associated with the network.

    var : :class:`~psynet.field.VarStore`
        A repository for arbitrary variables; see :class:`~psynet.field.VarStore` for details.
    """

    # pylint: disable=abstract-method

    __extra_vars__ = TrialNetwork.__extra_vars__.copy()

    participant_group = Column(String)
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

    def populate(self, stimulus_set, target_num_trials_per_stimulus):
        logger.info("Creating stimulus network (id = %i)...", self.id)
        source = TrialSource(network=self)
        db.session.add(source)
        stimuli = [
            x
            for x in stimulus_set.stimuli
            if x.phase == self.phase
            and x.participant_group == self.participant_group
            and x.block == self.block
        ]
        N = len(stimuli)
        n = 0
        for i, stimulus in enumerate(stimuli):
            stimulus.add_to_network(
                network=self,
                source=source,
                target_num_trials=target_num_trials_per_stimulus,
                stimulus_set=stimulus_set,
            )
            n = i + 1
            if n % 100 == 0:
                logger.info("Populated network %i with %i/%i stimuli...", self.id, n, N)
                db.session.commit()
        logger.info("Finished populating network %i with %i/%i stimuli.", self.id, n, N)
        db.session.commit()

    @property
    def stimulus_query(self):
        return Stimulus.query.filter_by(network_id=self.id)

    @property
    def stimuli(self):
        return self.stimulus_query.all()

    @property
    def num_stimuli(self):
        return self.stimulus_query.count()


class StimulusSetFromDir(StimulusSet):
    def __init__(
        self, id_: str, input_dir: str, media_ext: str, asset_label: str = "prompt"
    ):
        stimuli = []
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
                    stimuli.append(
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
        return super().__init__(id_, stimuli)
