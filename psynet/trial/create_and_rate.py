import inspect
from random import sample

import numpy as np
from dallinger import db
from dallinger.transformations import Transformation
from sqlalchemy import Column
from sqlalchemy.orm import declared_attr, deferred

from psynet.field import PythonObject
from psynet.trial import ChainNode
from psynet.trial.chain import ChainTrial
from psynet.trial.main import TrialMaker
from psynet.utils import get_logger

logger = get_logger()


def get_super_classes(cls):
    return inspect.getmro(cls)


def get_extended_class(obj):
    super_classes = get_super_classes(obj.__class__)
    mixin_class = super_classes[1]
    extended_class_idx = len(inspect.getmro(mixin_class))
    return super_classes[extended_class_idx]


def assert_correct_inheritance(sub_class, super_class):
    super_classes = get_super_classes(sub_class)
    assert len(super_classes) >= 3, "The class must inherit from at least two classes"
    error_msg = (
        "The mixin must be the first class you inherit from, for example:\n"
        "class CreateAndRateTrialMaker(CreateAndRateTrialMakerMixin, ImitationChainTrialMaker) would be correct and \n"
        "class CreateAndRateTrialMaker(ImitationChainTrialMaker, CreateAndRateTrialMakerMixin) would be incorrect."
    )
    assert super_classes[1] == super_class, error_msg


def filter_relevant_kwargs(kwargs, func):
    params = inspect.getfullargspec(func)
    keys = params.args + params.kwonlyargs
    return {key: kwargs[key] for key in keys if key in kwargs}


def get_required_parameters(func):
    inspected_function = inspect.getfullargspec(func)
    args = inspected_function.args + [
        arg
        for arg in inspected_function.kwonlyargs
        if arg not in inspected_function.kwonlydefaults
    ]
    args.remove("self")

    if inspected_function.defaults is None:
        return args
    else:
        return args[: -len(inspected_function.defaults)]


def split_kwargs(obj, kwargs, trial_maker_class, mixin_class):
    required_parameters = list(
        set(
            get_required_parameters(trial_maker_class.__init__)
            + get_required_parameters(obj.setup)
        )
    )
    for param in required_parameters:
        assert param in kwargs, f"Missing required parameter: {param}"
    trial_maker_kwargs = filter_relevant_kwargs(kwargs, trial_maker_class.__init__)
    mixin_kwargs = filter_relevant_kwargs(kwargs, mixin_class.setup)
    return trial_maker_kwargs, mixin_kwargs


class CreateAndRateTrialMixin(object):
    def __init__(self, experiment, node, participant, *args, **kwargs):
        trial_class = get_extended_class(self)
        assert issubclass(
            trial_class, ChainTrial
        ), "The trial class must inherit from ChainTrial"
        super().__init__(experiment, node, participant, *args, **kwargs)
        trial_class.__init__(self, experiment, node, participant, *args, **kwargs)


class CreateTrialMixin(CreateAndRateTrialMixin):
    pass


class RateOrSelectTrialMixin(CreateAndRateTrialMixin):
    def __init__(self, experiment, node, participant, *args, **kwargs):
        super().__init__(experiment, node, participant, *args, **kwargs)
        self.targets = self.get_targets()
        self.register_transformations(self.targets)

    @declared_attr
    def targets(cls):
        # See the mixin section of https://docs.sqlalchemy.org/en/14/orm/inheritance.html#resolving-column-conflicts
        # return deferred(Column(PythonObject))
        return deferred(cls.__table__.c.get("targets", Column(PythonObject)))

    def register_transformations(self, targets):
        # Register the transformations
        for target in targets:
            if issubclass(target.__class__, ChainTrial):
                transformation = Transformation(info_out=self, info_in=target)
                db.session.add(transformation)
        db.session.commit()

    def get_targets(self):
        return self.get_all_targets()

    def get_all_targets(self):
        trial_maker = self.trial_maker
        shuffle = trial_maker.randomize_target_presentation_order
        assert issubclass(trial_maker.__class__, CreateAndRateTrialMakerMixin)
        creator_class = trial_maker.creator_class
        targets = creator_class.query.filter_by(
            node_id=self.node_id, failed=False, finalized=True
        ).all()
        if self.trial_maker.include_previous_iteration:
            targets += [self.node]
        if shuffle:
            targets = sample(targets, len(targets))
        return targets

    def get_target_answer(self, target):
        if issubclass(target.__class__, ChainNode):
            return target.definition
        elif issubclass(target.__class__, ChainTrial):
            return target.answer
        else:
            raise NotImplementedError()


class SelectTrialMixin(RateOrSelectTrialMixin):
    def get_targets(self):
        assert self.trial_maker.target_selection_method == "all"
        return self.get_all_targets()

    def format_answer(self, answer, **kwargs):
        rated_target_strs = [f"{target}" for target in self.targets]
        assert (
            answer in rated_target_strs
        ), "The answer must be one of the rated target_strs"
        return answer


class RateTrialMixin(RateOrSelectTrialMixin):
    def get_targets(self):
        target_selection_method = self.trial_maker.target_selection_method
        if target_selection_method == "all":
            return self.get_all_targets()
        elif target_selection_method == "one":
            return self.get_one_target()
        else:
            raise NotImplementedError(
                f"Unknown rated_targets value: {target_selection_method}"
            )

    def count_rated_targets(self, available_targets_str):
        rater_class = self.trial_maker.rater_class
        all_rating_trials = rater_class.query.filter_by(
            node_id=self.node_id, failed=False
        ).all()
        all_rating_trials = [
            trial for trial in all_rating_trials if trial.id != self.id
        ]
        all_rated_target_strs = [
            f"{target}" for rating in all_rating_trials for target in rating.targets
        ]
        target2count = dict(
            zip(available_targets_str, [0] * len(available_targets_str))
        )
        for target_str in all_rated_target_strs:
            target2count[target_str] += 1
        return target2count

    def select_target_with_least_ratings(self, all_targets):
        all_targets_str = [f"{target}" for target in all_targets]
        target2count = self.count_rated_targets(all_targets_str)

        min_count = min(target2count.values())
        targets_with_min_count = [
            target_str
            for target_str, count in target2count.items()
            if count == min_count
        ]

        target_str_with_least_ratings = sample(targets_with_min_count, 1)[0]

        if self.trial_maker.verbose:
            logger.info(
                f"For network {self.network.id} at iteration {self.node.degree} we have the following"
                + f" ratings for: {target2count}. We therefore selected: {target_str_with_least_ratings}."
            )

        target_idx = all_targets_str.index(target_str_with_least_ratings)
        return all_targets[target_idx]

    def get_one_target(self):
        return [self.select_target_with_least_ratings(self.get_all_targets())]

    def format_answer(self, answer, **kwargs):
        rated_target_strs = [f"{target}" for target in self.targets]
        if len(self.targets) > 1:
            assert type(answer) == list, "The answer must be a list of ratings"
            assert len(answer) == len(
                self.targets
            ), "The answer must have the same length as the number of targets"
            assert all(
                [type(rating) in [int, float] for rating in answer]
            ), "The answer must be a list of numbers"
            answer = dict(zip(rated_target_strs, answer))
        else:
            if isinstance(answer, str):
                float_answer = float(answer)
                int_answer = int(answer)
                answer = float_answer if float_answer != int_answer else int_answer
            assert type(answer) in [int, float], "The answer must be a number"
            assert len(rated_target_strs) == 1
            answer = {rated_target_strs[0]: answer}
        return answer


class CreateAndRateNodeMixin(object):
    def __init__(self, **kwargs):
        extended_class = get_extended_class(self)
        assert issubclass(
            extended_class, ChainNode
        ), "The extended class must be a ChainNode"
        extended_class.__init__(self, **kwargs)

    def get_str2target(self, rate_or_select_trials):
        all_targets = rate_or_select_trials[0].get_all_targets()
        return {f"{target}": target for target in all_targets}

    def summarize_rate_trials(self, rate_trials):
        str2target = self.get_str2target(rate_trials)
        all_target_strs = list(str2target.keys())
        rating_dict = {target_str: [] for target_str in all_target_strs}
        for rate_trial in rate_trials:
            for target_str, rating in rate_trial.answer.items():
                rating_dict[target_str] += [rating]
        mean_rating_dict = {
            target_str: np.mean(ratings) for target_str, ratings in rating_dict.items()
        }
        target_str_with_highest_rating = max(mean_rating_dict, key=mean_rating_dict.get)

        if self.trial_maker.verbose:
            logger.info(
                f"For network {self.network_id} at iteration {self.degree} we have the following"
                + f" ratings for: {mean_rating_dict}. We therefore selected: {target_str_with_highest_rating}."
            )
        return str2target[target_str_with_highest_rating]

    def summarize_select_trials(self, select_trials):
        str2target = self.get_str2target(select_trials)
        count_dict = {target_str: 0 for target_str in str2target.keys()}
        for trial in select_trials:
            count_dict[trial.answer] += 1
        target_str_with_highest_count = max(count_dict, key=count_dict.get)
        if self.trial_maker.verbose:
            logger.info(
                f"For network {self.network_id} at iteration {self.degree} we have the following"
                + f" ratings for: {count_dict}. We therefore selected: {target_str_with_highest_count}."
            )
        return str2target[target_str_with_highest_count]

    def summarize_trials(self, trials, experiment, participant):
        trial_maker = self.trial_maker
        all_rate_trials = trial_maker.rater_class.query.filter_by(
            node_id=self.id, failed=False, finalized=True
        ).all()

        rate_mode = trial_maker.rate_mode

        if rate_mode == "rate":
            return self.summarize_rate_trials(all_rate_trials)
        elif rate_mode == "select":
            return self.summarize_select_trials(all_rate_trials)
        else:
            raise NotImplementedError(f"Unknown rate_mode value: {rate_mode}")


class CreateAndRateNode(CreateAndRateNodeMixin, ChainNode):
    def create_initial_seed(self, experiment, participant):
        return {}

    def create_definition_from_seed(self, seed, experiment, participant):
        return seed


class CreateAndRateTrialMakerMixin(object):
    def __init__(self, **kwargs):
        assert_correct_inheritance(self.__class__, CreateAndRateTrialMakerMixin)
        extended_class = get_extended_class(self)
        assert issubclass(
            extended_class, TrialMaker
        ), "The extended class must be a TrialMaker"
        trial_maker_kwargs, mixin_kwargs = self.prepare_kwargs(
            kwargs, extended_class, CreateAndRateTrialMakerMixin
        )
        self.setup(**mixin_kwargs)
        extended_class.__init__(self, **trial_maker_kwargs)

    def assert_correct_inheritance_elements(self):
        def check_inheritance(clc, base_class, mixin_class):
            assert issubclass(clc, mixin_class)
            assert issubclass(clc, base_class)

        check_inheritance(self.node_class, ChainNode, CreateAndRateNodeMixin)
        check_inheritance(self.creator_class, ChainTrial, CreateTrialMixin)
        if self.rate_mode == "select":
            check_inheritance(self.rater_class, ChainTrial, SelectTrialMixin)
        elif self.rate_mode == "rate":
            check_inheritance(self.rater_class, ChainTrial, RateTrialMixin)
        else:
            raise NotImplementedError(f"Unknown rate_mode value: {self.rate_mode}")

    def setup(
        self,
        n_creators,
        n_raters,
        node_class,
        creator_class,
        rater_class,
        start_nodes,
        rate_mode="rate",
        include_previous_iteration=False,
        target_selection_method="one",
        randomize_target_order=True,
        verbose=False,
    ):
        # Set class variables
        self.n_creators = n_creators
        self.n_raters = n_raters
        self.rate_mode = rate_mode
        self.creator_class = creator_class
        self.rater_class = rater_class
        self.node_class = node_class
        self.include_previous_iteration = include_previous_iteration
        self.n_rate_stimuli = self.n_creators + int(self.include_previous_iteration)
        self.target_selection_method = target_selection_method
        self.randomize_target_presentation_order = randomize_target_order
        self.verbose = verbose

        # Assertions
        self.assert_is_positive_integer(n_creators)
        self.assert_is_positive_integer(n_raters)
        self.assert_correct_inheritance_elements()

        if self.include_previous_iteration:
            error_msg = (
                "If you want to include previous iterations, you need to specify the seed, e.g."
                " CreateAndRateNode(seed='My initial response shown to the participant')"
            )
            n_nodes_with_seed = sum(
                [node.seed is not None and len(node.seed) > 0 for node in start_nodes]
            )
            assert len(start_nodes) == n_nodes_with_seed, error_msg

        if self.rate_mode == "rate":
            if self.target_selection_method == "one":
                if self.include_previous_iteration:
                    error_msg = (
                        "n_raters must be a multiple of n_creators + 1 (since include_previous_iteration == "
                        "True) if rate_mode is 'rate' and target_selection_method is 'one'."
                    )
                else:
                    error_msg = (
                        "n_raters must be a multiple of n_creators if rate_mode is 'rate' and "
                        "target_selection_method is 'one'."
                    )
                assert self.n_raters % (self.n_rate_stimuli) == 0, error_msg
                self.n_rate_stimuli = 1
        elif self.rate_mode == "select":
            assert (
                self.n_rate_stimuli > 1
            ), '`n_rate_stimuli` must be greater than 1 if `rate_mode` is "select"'
        else:
            raise NotImplementedError(f"Unknown rate_mode value: {rate_mode}")

        assert target_selection_method in ["one", "all"]

    @staticmethod
    def assert_is_positive_integer(x):
        assert type(x) == int and x > 0, f"{x} must be a positive integer"

    def prepare_kwargs(self, kwargs, trial_maker_class, mixin_class):
        kwargs["trial_class"] = kwargs["creator_class"]
        kwargs["node_class"] = kwargs["node_class"]
        trial_maker_kwargs, mixin_kwargs = split_kwargs(
            self, kwargs, trial_maker_class, mixin_class
        )
        trials_per_node = kwargs["n_creators"] + kwargs["n_raters"]
        trial_maker_kwargs["trials_per_node"] = trials_per_node
        return trial_maker_kwargs, mixin_kwargs

    def get_trial_class(self, node, participant, experiment):
        create_trials = self.get_non_failed_creations(node)
        finished_creations = self.get_finished_creations(node)
        need_creators = len(create_trials) < self.n_creators
        waiting_for_creators = len(finished_creations) < len(create_trials)

        if need_creators:
            return self.creator_class
        else:
            if waiting_for_creators:
                return None
            else:
                return self.rater_class

    def get_non_failed_creations(self, node):
        return self.creator_class.query.filter_by(node_id=node.id, failed=False).all()

    def get_finished_creations(self, node):
        return self.creator_class.query.filter_by(
            node_id=node.id, failed=False, finalized=True
        ).all()
