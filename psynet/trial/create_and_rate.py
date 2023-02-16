from random import sample

import numpy as np
from sqlalchemy import Column
from sqlalchemy.orm import declared_attr, deferred

from psynet.field import PythonObject
from psynet.trial import ChainNode
from psynet.trial.chain import ChainTrial
from psynet.utils import get_logger

logger = get_logger()

# Constants
RATE_MODES = ["rate", "select"]


def sort_dict_by_value(d):
    return dict(sorted(d.items(), key=lambda item: item[1]))


class CreateAndRateTrialMixin(object):
    trial_maker = None
    node = None
    node_id = None
    network = None

    # TODO: test if those properties are overriden by the child class?
    def __init__(self):
        super().__init__()


class CreateTrialMixin(CreateAndRateTrialMixin):
    pass


class RateOrSelectTrialMixin(CreateAndRateTrialMixin):
    # targets = deferred(Column(PythonObject))
    def __init__(self):
        super().__init__()
        self.targets = self.get_targets()

    __table_args__ = {"extend_existing": True}

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()

    @declared_attr
    def targets(cls):
        return deferred(Column(PythonObject))

    def get_targets(self):
        return self.get_all_targets()

    def get_all_targets(self):
        # TODO check if the querying works in inherited classes
        targets = self.__class__.query.filter_by(
            node_id=self.node_id, failed=False, finalized=True
        ).all()
        if self.trial_maker.include_previous_iteration:
            targets += self.node
        return targets

    @staticmethod
    def get_target_answer(target):
        if issubclass(target.__class__, ChainNode):
            return target.context["answer"]
        elif issubclass(target.__class__, ChainTrial):
            return target.answer
        else:
            raise NotImplementedError()

    @staticmethod
    def get_eid(entity):
        return f"{entity.__class__.__name__} {entity.id}"


class SelectTrialMixin(RateOrSelectTrialMixin):
    def get_targets(self):
        assert self.trial_maker.target_selection_method == "all"
        return self.get_all_targets()


class RateTrialMixin(RateOrSelectTrialMixin):
    def get_targets(self):
        target_selection_method = self.trial_maker.target_selection_method
        if target_selection_method == "all":
            return self.get_all_targets()
        # elif target_selection_method == 'random':
        #     return self.get_random_target()
        elif target_selection_method == "load_balanced":
            return self.get_load_balanced_target()
        else:
            raise NotImplementedError(
                f"Unknown rated_targets value: {target_selection_method}"
            )

    def get_all_targets(self, shuffle=True):

        trial_maker = self.trial_maker
        assert issubclass(trial_maker.__class__, CreateAndRateTrialmakerMixin)
        creator_class = trial_maker.creator_class
        targets = creator_class.query.filter_by(
            node_id=self.node_id, failed=False, finalized=True
        ).all()
        if self.trial_maker.include_previous_iteration:
            targets += self.node
        if shuffle:
            targets = sample(targets, len(targets))
        return targets

    # def get_random_target(self):
    #     return sample(self.get_all_targets(), 1)

    def get_eids_from_entities(self, entities):
        return [self.get_eid(entity) for entity in entities]

    def count_rated_creations(self, available_creation_eids):
        rater_class = self.trial_maker.rater_class
        all_rating_trials = rater_class.query.filter_by(
            node_id=self.node_id, failed=False
        ).all()
        all_rated_creation_eids = [
            self.get_eid(creation)
            for rating in all_rating_trials
            for creation in rating.targets
        ]
        rated_creations = dict(
            zip(available_creation_eids, [0] * len(available_creation_eids))
        )
        for creation_eid in all_rated_creation_eids:
            rated_creations[creation_eid] += 1
        return rated_creations

    def select_creation_with_least_ratings(self, all_creation_trials):
        all_creation_eids = self.get_eids_from_entities(all_creation_trials)
        rated_creations = self.count_rated_creations(all_creation_eids)

        creation_eid_with_least_ratings = min(rated_creations, key=rated_creations.get)

        if self.trial_maker.verbose:
            logger.info(
                f"For network {self.network.id} at iteration {self.node.degree} we have the following"
                + f" ratings for: {rated_creations}. We therefore selected: {creation_eid_with_least_ratings}."
            )

        creation_idx = all_creation_eids.index(creation_eid_with_least_ratings)
        return all_creation_trials[creation_idx]

    def get_load_balanced_target(self):
        # TODO to test in a real experiment
        return [self.select_creation_with_least_ratings(self.get_all_targets())]


class CreateAndRateNodeMixin(object):
    @staticmethod
    def get_eid_mapping_from_trials(trials):
        trial = trials[0]
        all_targets = trial.get_all_targets()
        all_target_eids = [trial.get_eid(target) for target in all_targets]
        return dict(zip(all_target_eids, all_targets))

    @staticmethod
    def summarize_rate_trials(node, rate_trials):
        eid2target = CreateAndRateNodeMixin.get_eid_mapping_from_trials(rate_trials)
        all_target_eids = list(eid2target.keys())
        rating_dict = {eid: [] for eid in all_target_eids}
        for rate_trial in rate_trials:
            for eid, rating in rate_trial.answer.items():
                rating_dict[eid] += [rating]
        mean_rating_dict = {
            eid: np.mean(ratings) for eid, ratings in rating_dict.items()
        }
        eid_with_highest_rating = max(mean_rating_dict, key=mean_rating_dict.get)

        if node.trial_maker.verbose:
            logger.info(
                f"For network {node.network_id} at iteration {node.degree} we have the following"
                + f" ratings for: {mean_rating_dict}. We therefore selected: {eid_with_highest_rating}."
            )
        return eid2target[eid_with_highest_rating]

    @staticmethod
    def summarize_select_trials(node, select_trials):
        eid2target = CreateAndRateNodeMixin.get_eid_mapping_from_trials(select_trials)
        count_dict = {eid: 0 for eid in eid2target.keys()}
        for trial in select_trials:
            count_dict[trial.answer] += 1
        eid_with_highest_count = max(count_dict, key=count_dict.get)
        if node.trial_maker.verbose:
            logger.info(
                f"For network {node.network_id} at iteration {node.degree} we have the following"
                + f" ratings for: {count_dict}. We therefore selected: {eid_with_highest_count}."
            )
        return eid2target[eid_with_highest_count]

    @staticmethod
    def summarize_trials(node):
        node_class = node.__class__
        all_rate_trials = node_class.query.filter_by(
            node_id=node.id, failed=False, finalized=True
        ).all()
        unique_rate_classes = set([type(trial) for trial in all_rate_trials])
        assert (
            len(unique_rate_classes) == 1
        ), f"You can't mix create and select trials, we got {unique_rate_classes}"

        rate_mode = node.trial_maker.rate_mode

        if rate_mode == "rate":
            return CreateAndRateNodeMixin.summarize_rate_trials(node, all_rate_trials)
        elif rate_mode == "select":
            return CreateAndRateNodeMixin.summarize_select_trials(node, all_rate_trials)
        else:
            raise NotImplementedError(f"Unknown rate_mode value: {rate_mode}")


class CreateAndRateNode(ChainNode, CreateAndRateNodeMixin):
    def summarize_trials(self, trials: list, experiment, participant):
        return CreateAndRateNodeMixin.summarize_trials(self)

    def create_initial_seed(self, experiment, participant):
        return None

    def create_definition_from_seed(self, seed, experiment, participant):
        return None


class CreateAndRateTrialmakerMixin(object):
    def __init__(
        self,
        num_creators,
        num_raters,
        node_class,
        creator_class,
        rater_class,
        rate_mode="rate",
        include_previous_iteration=False,
        target_selection_method="load_balanced",
        verbose=True,  # TODO turn off in production
    ):
        self.assert_is_positive_integer(num_creators)
        self.num_creators = num_creators
        self.assert_is_positive_integer(num_raters)
        self.num_raters = num_raters

        self.assert_correct_inheritance(creator_class, ChainTrial, CreateTrialMixin)
        self.creator_class = creator_class

        self.assert_correct_inheritance(rater_class, ChainTrial, RateTrialMixin)
        self.rater_class = rater_class

        self.assert_correct_inheritance(node_class, ChainNode, CreateAndRateNodeMixin)
        self.node_class = node_class

        assert rate_mode in ["rate", "select"]
        self.rate_mode = rate_mode
        self.include_previous_iteration = include_previous_iteration
        if self.rate_mode == "select":
            self.num_rate_stimuli = self.num_creators + int(
                self.include_previous_iteration
            )
            self.num_validations_per_creation = self.num_creators
        elif self.rate_mode == "rate":
            if self.include_previous_iteration:
                assert (
                    self.num_raters % (self.num_creators + 1) == 0
                ), "num_raters must be a multiple of num_creators + 1 (since include_previous_iteration == True) if rate_mode is 'rate'"
            else:
                assert (
                    self.num_raters % self.num_creators == 0
                ), "num_raters must be a multiple of num_creators if rate_mode is 'rate'"
            self.num_rate_stimuli = 1
            self.num_validations_per_creation = self.num_raters // self.num_creators

        else:
            raise ValueError(f"rate_mode must be in {RATE_MODES}")

        if self.rate_mode == "select":
            assert (
                self.num_rate_stimuli > 1
            ), '`num_rate_stimuli` must be greater than 1 if `rate_mode` is "select"'

        assert target_selection_method in ["load_balanced", "random", "all"]
        self.target_selection_method = target_selection_method
        self.verbose = verbose

    @staticmethod
    def assert_is_positive_integer(x):
        assert type(x) == int and x > 0, f"{x} must be a positive integer"

    @staticmethod
    def assert_correct_inheritance(clc, base_class, mixin_class):
        assert issubclass(clc, mixin_class)
        assert issubclass(clc, base_class)

    def update_trial_maker_kwargs(self, trial_maker_kwargs):
        trials_per_node = self.num_creators + self.num_raters
        trial_maker_kwargs["trials_per_node"] = trials_per_node
        trial_maker_kwargs["trial_class"] = self.creator_class
        trial_maker_kwargs["node_class"] = trial_maker_kwargs.get(
            "node_class", self.node_class
        )
        return trial_maker_kwargs

    def get_role(self, node, participant, experiment):
        create_trials = self.get_non_failed_creations(node)
        finished_creations = self.filter_finished_creations(create_trials)
        need_creators = len(create_trials) < self.num_creators
        waiting_for_creators = len(finished_creations) < len(create_trials)

        if need_creators:
            return self.creator_class
        else:
            if waiting_for_creators:
                return None
            else:
                return self.rater_class

    @staticmethod
    def finalize_create_and_rate_trial(trial_maker, trial):
        answer = trial.answer
        if issubclass(trial.__class__, trial_maker.rater_class):
            rated_eids = [trial.get_eid(target) for target in trial.targets]
            rate_mode = trial_maker.rate_mode
            if rate_mode == "rate":
                if len(trial.targets) > 1:
                    assert type(answer) == list, "The answer must be a list of ratings"
                    assert len(answer) == len(
                        rated_eids
                    ), "The answer must have the same length as the number of targets"
                    assert all(
                        [type(rating) in [int, float] for rating in answer]
                    ), "The answer must be a list of numbers"
                    answer = dict(zip(rated_eids, answer))
                else:
                    assert type(answer) in [int, float], "The answer must be a number"
                    assert len(rated_eids) == 1
                    answer = {rated_eids[0]: answer}
            elif rate_mode == "select":
                assert answer in rated_eids, "The answer must be one of the rated eids"
        return answer

    def get_non_failed_creations(self, node):
        return [
            trial
            for trial in node.all_trials
            if isinstance(trial, self.creator_class) and trial.failed is False
        ]

    def filter_finished_creations(self, trials):
        return [
            trial
            for trial in trials
            if trial.answer is not None and trial.finalized is True
        ]

    def get_finished_creations(self, node):
        trials = self.get_non_failed_creations(node)
        return self.filter_finished_creations(trials)
