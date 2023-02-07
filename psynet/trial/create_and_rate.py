import collections

from psynet.timeline import FailedValidation
from psynet.trial.imitation_chain import ImitationChainNode
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


class CreateAndRateTrial:
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

    def is_create_trial(self, trial):
        if not (trial.var.has(ROLE_KEY) and trial.var.has(ROLE_ID_KEY)):
            infos_at_iter = trial.node.infos()
            info_dict = {info.id: info for info in infos_at_iter}
            # Sort the values
            infos_at_iter = list(sort_dict_by_key(info_dict).values())
            creation_trials = [
                info
                for info in infos_at_iter
                if info.var.has(ROLE_KEY)
                and info.var.get(ROLE_KEY) == CREATOR_KEY
                and not info.failed
                and info.id != trial.id
            ]

            trial_maker = self.trial_maker
            num_creators = trial_maker.num_creators

            # TODO for future: you do not have to wait for all creations to be finished if rate_mode == "select",
            #  however this will require some additional bookkeeping. I.e., once you register a creation to one rater,
            #  it needs to be blocked until it finished or timed out.
            if len(creation_trials) < num_creators:
                taken_roles = [
                    creation_trial.var.get(ROLE_ID_KEY)
                    for creation_trial in creation_trials
                ]
                possible_roles = [f"creation{i + 1}" for i in range(num_creators)]
                available_roles = [
                    _id for _id in possible_roles if _id not in taken_roles
                ]
                trial.var.set(ROLE_KEY, CREATOR_KEY)
                role = available_roles[0]
            else:
                trial.var.set(ROLE_KEY, RATER_KEY)
                raters = [
                    info
                    for info in infos_at_iter
                    if info.var.has(ROLE_KEY)
                    and info.var.get(ROLE_KEY) == RATER_KEY
                    and not info.failed
                ]
                role = f"rating{len(raters) + 1}"

                creations_to_validate = []

                if trial_maker.rate_mode == "select":
                    if trial_maker.include_previous_iteration:
                        creations_to_validate.append(self.get_previous_iteration(self))
                    for creation_trial in creation_trials:
                        creations_to_validate.append(self.get_creation(creation_trial))
                else:
                    keys = [f"creation{i + 1}" for i in range(num_creators)]
                    if trial_maker.include_previous_iteration:
                        keys.append("previous_iteration")

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

                    logger.info(
                        f"""For network {self.network_id} at iteration {self.node.degree} we have the following
                    ratings for: {rating_count_dict}. We therefore selected: {key}."""
                    )

                    # nth_rating = rating_count_dict[key] + 1
                    if key == "previous_iteration":
                        # _id = f"rating{nth_rating}_previous_iteration"
                        creation = self.get_previous_iteration(self)
                    elif key.startswith("creation"):
                        nth_creation = int(key.replace("creation", ""))
                        # _id = f"rating{nth_rating}_creation{nth_creation}"
                        selected_creation = [
                            creation
                            for creation in creation_trials
                            if creation.var.get(ROLE_ID_KEY)
                            == f"creation{nth_creation}"
                        ]
                        assert len(selected_creation) == 1
                        creation = self.get_creation(selected_creation[0])
                    else:
                        raise Exception(f"Unknown key: {key}")
                    creations_to_validate.append(creation)

                assert len(creations_to_validate) > 0
                trial.var.set("creations_to_validate", creations_to_validate)

            trial.var.set(ROLE_ID_KEY, role)
            logger.info(f"""We assign role ID '{role}' to Trial {trial.id}""")
        if trial.var.has(ROLE_KEY) and trial.var.has(ROLE_ID_KEY):
            is_creator = trial.var.get(ROLE_KEY) == CREATOR_KEY

            return is_creator
        else:
            # TODO not sure how to deal with this as it causes a runtime error…
            raise FailedValidation(f"""Trial {trial.id} has no type or role""")


class CreateAndRateNode(ImitationChainNode):
    def create_initial_seed(self, experiment, participant):
        # TODO I don't think this is needed anymore cause we provide the initial node list…
        return None

    def summarize_trials(self, trials: list, experiment, participant):
        # TODO implement this
        # If max_nodes_per_chain == 1, return None
        # Else, check if mode is RATER_KEY or CREATOR_KEY
        return None


class CreateAndRateTrialMaker:
    num_creators = None  # Number of creators
    num_raters = None  # Number of raters
    rate_mode = "rate"  # Either "rate" each stimulus is rated individually or "select" where each rater selects one stimulus
    num_rate_stimuli = None  # Number of stimuli to rate, TODO not implemented yet
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

        assert self.num_rate_stimuli is None, "num_rate_stimuli is not implemented yet"
        if self.rate_mode == "select":
            self.num_rate_stimuli = self.num_creators
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

    def filter_networks(self, networks, participant, experiment):
        if self.role_separation:
            # TODO skip if participant has already been assigned a role
            # TODO estimate the need of creators and raters
            participant.set(self.role_separation_var_name, CREATOR_KEY)

        new_networks = []

        # TODO implement role_separation

        for network in networks:
            if len(network.all_infos) == 0:
                # I.e., empty network
                new_networks.append(network)
            else:
                if not all([info.var.has(ROLE_KEY) for info in network.all_infos]):
                    # TODO test
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
                    new_networks.append(network)

        return new_networks
