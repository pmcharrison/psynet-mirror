import collections
from typing import List

import numpy as np
from markupsafe import Markup

from psynet.modular_page import PushButtonControl
from psynet.timeline import Event, FailedValidation, ProgressDisplay, ProgressStage
from psynet.utils import get_logger

logger = get_logger()


def sort_dict_by_key(d):
    return dict(sorted((d.items())))


def sort_dict_by_value(d):
    return dict(sorted(d.items(), key=lambda item: item[1]))


CREATOR_KEY = "creator"
RATER_KEY = "rater"
ROLE_ID_KEY = "role_id"
ROLE_KEY = "role"

PREVIOUS_ITERATION_KEY = "previous_iteration"
CREATION_KEY = "creation"


class CreateAndRateTrial(object):
    def show_create_trial(self):
        raise NotImplementedError

    def show_rate_trial(self):
        raise NotImplementedError

    @staticmethod
    def get_previous_iteration(trial):
        return trial.origin.definition

    @staticmethod
    def get_creation(create_trial):
        return create_trial.answer

    def get_trials_at_iteration(self):
        infos_at_iter = self.node.infos()
        info_dict = {info.id: info for info in infos_at_iter}
        # Sort the values
        return list(sort_dict_by_key(info_dict).values())

    def get_creation_trials(self, trials):
        return [
            info
            for info in trials
            if info.var.has(ROLE_KEY)
            and info.var.get(ROLE_KEY) == CREATOR_KEY
            and not info.failed
            and info.id != self.id
        ]

    def is_create_trial(self):
        if not (self.var.has(ROLE_KEY) and self.var.has(ROLE_ID_KEY)):
            # The assignment of roles is done once, to avoid flickering between roles
            trials = self.get_trials_at_iteration()
            creation_trials = self.get_creation_trials(trials)

            trial_maker = self.trial_maker
            num_creators = trial_maker.num_creators

            if len(creation_trials) < num_creators:
                taken_roles = [
                    creation_trial.var.get(ROLE_ID_KEY)
                    for creation_trial in creation_trials
                ]
                possible_roles = [f"{CREATION_KEY}{i + 1}" for i in range(num_creators)]
                available_roles = [
                    _id for _id in possible_roles if _id not in taken_roles
                ]
                self.var.set(ROLE_KEY, CREATOR_KEY)
                role = available_roles[0]
            else:
                self.var.set(ROLE_KEY, RATER_KEY)
                raters = [
                    trial
                    for trial in trials
                    if trial.var.has(ROLE_KEY)
                    and trial.var.get(ROLE_KEY) == RATER_KEY
                    and not trial.failed
                ]

                creations_to_validate = []
                creation_keys_to_validate = []

                if trial_maker.rate_mode == "select":
                    role = f"rating{len(raters)}"
                    if trial_maker.include_previous_iteration:
                        creations_to_validate.append(self.get_previous_iteration(self))
                        creation_keys_to_validate.append(PREVIOUS_ITERATION_KEY)
                    for idx, creation_trial in enumerate(creation_trials):
                        creations_to_validate.append(self.get_creation(creation_trial))
                        creation_keys_to_validate.append(f"{CREATION_KEY}{idx + 1}")
                else:
                    keys = [f"creation{i + 1}" for i in range(num_creators)]
                    if trial_maker.include_previous_iteration:
                        keys.append(PREVIOUS_ITERATION_KEY)

                    rating_count_dict = {}
                    for key in keys:
                        rating_count_dict[key] = sum(
                            [
                                1
                                for rater in raters
                                if rater.var.has(ROLE_ID_KEY)
                                and rater.var.get(ROLE_ID_KEY).endswith(key)
                            ]
                        )

                    rating_count_dict = sort_dict_by_value(rating_count_dict)
                    key = list(rating_count_dict.keys())[
                        0
                    ]  # prioritize the one with the smallest number of ratings

                    role = f"rating{len(raters)}_{key}"

                    logger.info(
                        f"""For network {self.network_id} at iteration {self.node.degree} we have the following
                    ratings for: {rating_count_dict}. We therefore selected: {key}."""
                    )

                    # nth_rating = rating_count_dict[key] + 1
                    if key == PREVIOUS_ITERATION_KEY:
                        creation = self.get_previous_iteration(self)
                    elif key.startswith(CREATION_KEY):
                        nth_creation = int(key.replace(CREATION_KEY, ""))
                        selected_creation = [
                            creation
                            for creation in creation_trials
                            if creation.var.get(ROLE_ID_KEY)
                            == f"{CREATION_KEY}{nth_creation}"
                        ]
                        assert len(selected_creation) == 1
                        creation = self.get_creation(selected_creation[0])
                    else:
                        raise Exception(f"Unknown key: {key}")
                    creations_to_validate.append(creation)

                assert len(creations_to_validate) > 0
                self.var.set("creations_to_validate", creations_to_validate)

            self.var.set(ROLE_ID_KEY, role)
            logger.info(f"""We assign role ID '{role}' to Trial {self.id}""")
        if self.var.has(ROLE_KEY) and self.var.has(ROLE_ID_KEY):
            is_creator = self.var.get(ROLE_KEY) == CREATOR_KEY
            return is_creator
        else:
            # TODO not sure how to deal with this as it causes a runtime error…
            raise FailedValidation(f"""Trial {self.id} has no type or role""")

    @staticmethod
    def autoplay_media(
        media_type,
        media_keys,
        media_duration,
        base_label="Recording",
        reorder_list=None,
        stage_colors=["blue", "red"],
    ):
        assert media_type in ["audio", "video"]

        if type(reorder_list) == list:
            media_keys = [media_keys[i] for i in reorder_list]

        # Prepare events and stages
        # disable all buttons before start
        events = {
            "hideButtons": Event(
                is_triggered_by="trialStart",
                js="document.getElementsByClassName('push-button-container')[0].hidden = true",
            )
        }
        stages = []
        time_past = 0
        count = 0
        for idx, media_key in enumerate(media_keys):
            # Alternate colors
            color_idx = count % len(stage_colors)
            color = stage_colors[color_idx]
            label = f"{base_label} {idx + 1}"
            stages.append(
                ProgressStage(media_duration, Markup(f"""Listen to {label}"""), color)
            )

            media_key = media_keys[idx]
            key = "play_" + media_key
            events[key] = Event(
                is_triggered_by="trialStart",
                delay=time_past,
                js="psynet."
                + media_type
                + "."
                + media_key.replace(" ", "_").lower()
                + ".play()",
            )
            time_past += media_duration
            count += 1

        # enable the buttons
        events["showButtons"] = Event(
            is_triggered_by="trialStart",
            delay=time_past,
            js="document.getElementsByClassName('push-button-container')[0].hidden = false",
        )
        progress_display = ProgressDisplay(stages=stages)
        return events, progress_display


class RateControl(PushButtonControl):
    def __init__(
        self,
        choices: List[int],
        labels: List[str] = None,
        style: str = "min-width: 100px; margin: 10px",
        arrange_vertically: bool = True,
        **kwargs,
    ):
        assert all(
            [isinstance(choice, int) for choice in choices]
        ), "Choices must be integers"
        super().__init__(choices, labels, style, arrange_vertically, **kwargs)


class SelectControl(RateControl):
    def __init__(
        self,
        reorder_list: List[int],
        base_label="Recording",
        style: str = "min-width: 100px; margin: 10px",
        arrange_vertically: bool = True,
    ):
        ordered_choices = sorted(reorder_list)
        assert (
            ordered_choices[0] == 0
        ), "Choices must start at 0 as they are used as indices"
        assert all(
            np.diff(ordered_choices) == 1
        ), f"Choices must be consecutive, got: {ordered_choices}"
        labels = [f"{base_label} {i + 1}" for i in ordered_choices]
        super().__init__(reorder_list, labels, style, arrange_vertically)


class CreateAndRateNode(object):
    def __init__(self):
        pass

    @staticmethod
    def get_rating_trials(trials):
        return [
            trial
            for trial in trials
            if trial.var.has(ROLE_KEY) and trial.var.get(ROLE_KEY) == RATER_KEY
        ]

    @staticmethod
    def get_mean_rating(trials, key):
        rating_trials = CreateAndRateNode.get_rating_trials(trials)
        return np.array(
            [
                int(t.answer)
                for t in rating_trials
                if t.var.get(ROLE_ID_KEY).endswith(key)
            ]
        ).mean()

    def get_next_creation(self, trials: list):
        trial_maker = self.trial_maker
        finished_creations = [
            trial
            for trial in trials
            if not trial.failed
            and trial.var.has(ROLE_KEY)
            and trial.var.get(ROLE_KEY) == CREATOR_KEY
            and trial.answer is not None
        ]
        num_creators = trial_maker.num_creators
        included_previous_iteration = trial_maker.include_previous_iteration
        rated_creations = finished_creations
        if included_previous_iteration:
            previous_creation = finished_creations[
                0
            ].node  # TODO not sure if this is valid for all use cases
            rated_creations = [previous_creation] + rated_creations
        assert len(finished_creations) == num_creators

        if trial_maker.rate_mode == "select":
            rating_trials = CreateAndRateNode.get_rating_trials(trials)
            answers = [
                trial.var.reorder_list[int(trial.answer)] for trial in rating_trials
            ]
            c = collections.Counter(answers)
            counts = list(c.values())
            keys = list(c.keys())
            idx = keys[np.argmax(counts)]
            return rated_creations[idx]
        else:
            mean_ratings = []
            rated_items = []
            if included_previous_iteration:
                mean_ratings.append(
                    CreateAndRateNode.get_mean_rating(trials, PREVIOUS_ITERATION_KEY)
                )
                rated_items.append(PREVIOUS_ITERATION_KEY)
            for i in range(trial_maker.num_creators):
                nth_creator = i + 1
                current_creation_key = f"{CREATION_KEY}{nth_creator}"
                mean_ratings.append(
                    CreateAndRateNode.get_mean_rating(trials, current_creation_key)
                )
                rated_items.append(current_creation_key)

            observation_idx = mean_ratings.index(max(mean_ratings))
            selected_item = rated_items[observation_idx]
            rating_dict = dict(zip(rated_items, mean_ratings))
            logger.info(
                f"""
                    For network {self.network_id} at iteration {self.degree} we obtained the following average
                     ratings: {rating_dict}. We therefore selected: {selected_item}.
                    """
            )

            return rated_creations[observation_idx]


class CreateAndRateTrialMaker(object):
    num_creators = None  # Number of creators
    num_raters = None  # Number of raters
    rate_mode = "rate"  # Either "rate" each stimulus is rated individually or "select" where each rater selects one stimulus
    include_previous_iteration = (
        False  # Whether to include the previous iteration in the rate trial
    )
    role_separation = False  # Whether to separate the roles of creators and raters, TODO to be implemented
    role_separation_var_name = (
        None  # default is participant.var.get(trialmaker id + '_role_separation')
    )

    def __init__(self, id_):
        assert (
            type(self.num_creators) == int and self.num_creators > 0
        ), "num_creators must be a positive integer"
        assert (
            type(self.num_raters) == int and self.num_raters > 0
        ), "num_raters must be a positive integer"
        RATE_MODES = ["rate", "select"]

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

        assert type(self.role_separation) == bool, "role_separation must be a boolean"
        assert (
            self.trials_per_node == self.num_creators + self.num_raters
        ), "trials_per_node must be equal to num_creators + num_raters"
        if self.role_separation_var_name is None:
            self.role_separation_var_name = f"{id_}_role_separation"

    def get_iteration_and_finished_trials_from_network(self, network):
        if len(network.all_infos) == 0:
            return 1, []
        else:
            iteration = max([info.node.degree for info in network.all_infos])
            finished_trials_at_iter = [
                info
                for info in network.all_infos
                if info.node.degree == iteration
                and info.var.has(ROLE_KEY)
                and not info.failed
                and info.answer is not None
            ]
            counter = collections.Counter(
                [trial.var.get(ROLE_KEY) for trial in finished_trials_at_iter]
            )
            if (
                counter[CREATOR_KEY] == self.num_creators
                and counter[RATER_KEY] == self.num_raters
            ):
                # This means the old iteration is already full, so there are no finished_trials_at_iter at the current level
                return iteration + 1, []
            else:
                return iteration, finished_trials_at_iter

    def store_visited_networks(self, trial, participant):
        visited_networks = participant.var.get("visited_networks", {})
        net_key = str(trial.network_id)
        if net_key not in visited_networks:
            visited_networks[net_key] = []
        trial_role = trial.var.get(ROLE_KEY)
        visited_networks[net_key].append(trial_role)
        participant.var.set("visited_networks", visited_networks)

    def filter_networks(
        self, networks, participant, allow_revisit_with_different_role=False
    ):
        if type(networks) is str:
            # return "exit", "wait"
            return networks

        visited_networks = {}
        if allow_revisit_with_different_role:
            assert (
                self.allow_revisiting_networks_in_across_chains is True
            ), "allow_revisit_with_different_role is only possible if allow_revisiting_networks_in_across_chains is True"
            visited_networks = participant.var.get("visited_networks", {})

        # TODO implement role_separation
        role_name = None
        if self.role_separation:
            # TODO skip if participant has already been assigned a role
            # TODO estimate the need of creators and raters
            participant.set(self.role_separation_var_name, CREATOR_KEY)

            role_name = participant.get(self.role_separation_var_name)

        new_networks = []

        for network in networks:
            if len(network.all_infos) == 0:
                # I.e., empty network
                new_networks.append(network)
            else:
                if not all([info.var.has(ROLE_KEY) for info in network.all_infos]):
                    # If there are undefined infos for a network skip it for now
                    continue

                iteration, _ = self.get_iteration_and_finished_trials_from_network(
                    network
                )
                pending_and_finished_creations = [
                    info
                    for info in network.all_infos
                    if info.node.degree == iteration
                    and not info.failed
                    and info.var.has(ROLE_KEY)
                    and info.var.get(ROLE_KEY) == CREATOR_KEY
                ]
                n_promised_creations = len(pending_and_finished_creations)
                n_pending_creations = sum(
                    [
                        creator.answer is None
                        for creator in pending_and_finished_creations
                    ]
                )

                pending_and_finished_ratings = [
                    info
                    for info in network.all_infos
                    if info.node.degree == iteration
                    and not info.failed
                    and info.var.has(ROLE_KEY)
                    and info.var.get(ROLE_KEY) == RATER_KEY
                ]
                n_promised_ratings = len(pending_and_finished_ratings)
                n_pending_ratings = sum(
                    [rater.answer is None for rater in pending_and_finished_ratings]
                )

                if (
                    n_promised_creations == self.num_creators
                    and n_pending_creations > 0
                ):
                    # If all creations have already been assigned, but not all workers are done, we have to wait for
                    # the last creator to finish
                    logger.info(
                        f"Skipping network {network.id} with {n_pending_creations}/{n_promised_creations} pending creations."
                    )
                elif n_promised_ratings == self.num_raters and n_pending_ratings > 0:
                    # We'll wait for the last rater to be done
                    logger.info(
                        f"Skipping network {network.id} with {n_pending_ratings}/{n_promised_ratings} pending ratings."
                    )
                else:
                    network_state = (
                        CREATOR_KEY
                        if n_promised_creations < self.num_creators
                        else RATER_KEY
                    )
                    net_key = str(network.id)
                    skip_network = (
                        allow_revisit_with_different_role
                        and net_key in visited_networks
                        and network_state in visited_networks[net_key]
                    )
                    if skip_network:
                        continue

                    if self.role_separation:
                        if role_name == CREATOR_KEY and network_state == CREATOR_KEY:
                            new_networks.append(network)
                        elif role_name == RATER_KEY and network_state == RATER_KEY:
                            new_networks.append(network)
                        else:
                            logger.warning(f"Unknown role {role_name}")
                    else:
                        new_networks.append(network)
        if len(new_networks) == 0:
            return "exit"
        else:
            return new_networks
