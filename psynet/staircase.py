from typing import Optional, Type, Union

from sqlalchemy import Column, Float, Integer

from psynet.trial import ChainNode, ChainTrial
from psynet.trial.chain import ChainTrialMaker


class GeometricStaircaseNode(ChainNode):
    # k up 2 down procedure
    k = 2

    n_consecutive_correct = Column(Integer)
    parameter = Column(Float)
    run_number = Column(Integer)

    def __init__(self, *args, parameter=None, run_number=None, **kwargs):
        self.parameter = parameter
        self.run_number = run_number
        super().__init__(*args, **kwargs)

    # todo - migrate this code to init

    def init_next_node(self, next_node: ChainNode):
        assert self.network.chain_type == "within"

        if self.degree == 0:
            self.n_consecutive_correct = 0

        next_node.run_number = self.run_number
        next_node.parameter = self.parameter
        next_node.n_consecutive_correct = self.n_consecutive_correct

        if self.trial.score == 1:
            next_node.n_consecutive_correct += 1

            if next_node.n_consecutive_correct == self.k:
                next_node.increase_difficulty()
                next_node.n_consecutive_correct = 0

        elif self.trial.score == 0:
            next_node.decrease_difficulty()
            next_node.n_consecutive_correct = 0

        else:
            raise ValueError(f"Unexpected score: {self.trial.score}")

    @property
    def definition(self):
        return {"parameter": self.parameter}

    def increase_difficulty(self):
        raise NotImplementedError()

    def decrease_difficulty(self):
        raise NotImplementedError()

    def create_seed(self, experiment, participant):
        return {}


class GeometricStaircaseTrial(ChainTrial):
    parameter = Column(Float)

    def __init__(self, *args, **kwargs):
        self.parameter = kwargs["node"].parameter
        super().__init__(*args, **kwargs)

    def make_definition(self, experiment, participant):
        return {"parameter": self.node.parameter}


class GeometricStaircaseTrialMaker(ChainTrialMaker):
    def __init__(
        self,
        *,
        id_,
        trial_class: Type[GeometricStaircaseTrial],
        node_class: Type[GeometricStaircaseNode],
        start_parameter: Union[int, float, callable],
        n_runs: int,
        max_trials_per_run: int,
        max_reversals_per_run: Optional[int] = None,
        mix_runs: bool = False,
        balance_mixed_runs: bool = False,
        expected_trials_per_participant: Optional[int] = None,
        target_n_participants: Optional[int] = None,
        recruit_mode: str = "n_participants",
        assets=None,
        choose_participant_group: Optional[callable] = None,
        sync_group_type: Optional[str] = None,
    ):
        self.n_runs = n_runs
        self.max_trials_per_run = max_trials_per_run
        self.max_reversals_per_run = max_reversals_per_run  # TODO
        self.mix_runs = mix_runs
        self.balance_mixed_runs = balance_mixed_runs
        self.start_parameter = start_parameter

        if expected_trials_per_participant is None:
            if max_reversals_per_run is None:
                expected_trials_per_participant = n_runs * max_trials_per_run
            else:
                raise ValueError(
                    "expected_trials_per_participant needs to be specified."
                )

        super().__init__(
            id_=id_,
            trial_class=trial_class,
            node_class=node_class,
            network_class=None,
            chain_type="within",
            target_n_participants=target_n_participants,
            recruit_mode=recruit_mode,
            start_nodes=self.get_start_nodes,
            trials_per_node=1,
            expected_trials_per_participant=expected_trials_per_participant,
            assets=assets,
            choose_participant_group=choose_participant_group,
            sync_group_type=sync_group_type,
            max_nodes_per_chain=max_trials_per_run,
            check_performance_at_end=True,
            check_performance_every_trial=False,
            balance_across_chains=balance_mixed_runs,
        )

    def get_start_nodes(self, participant):
        if callable(self.start_parameter):
            parameter = self.start_parameter(participant=participant)
        else:
            parameter = self.start_parameter

        return [
            self.node_class(
                parameter=parameter,
                run_number=run_number,
                block="default" if self.mix_runs else str(run_number),
            )
            for run_number in range(self.n_runs)
        ]

    def performance_check(self, experiment, participant, participant_trials):
        """Should return a dict: {"score": float, "passed": bool}"""
        # score = 0
        # failed = False
        # for trial in participant_trials:
        #     if trial.answer == "Not at all":
        #         failed = True
        #     else:
        #         score += 1
        # return {"score": score, "passed": not failed}


# To do - implement estimator
# see https://cran.r-project.org/web/packages/upndown/vignettes/upndown_basics.html
# simple version: averaging reversals
# complex version: use the upndown R package via rpy2

# To do - implement stopping rule
# To do - implement graph
