from statistics import mean
from typing import Optional, Type, Union

from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer
from sqlalchemy.orm import relationship

from .field import PythonObject
from .trial.chain import ChainNetwork, ChainNode, ChainTrial, ChainTrialMaker


class GeometricStaircaseNode(ChainNode):
    # k up 2 down procedure
    k = 2

    n_consecutive_correct = Column(Integer)
    parameter = Column(PythonObject)
    reversal = Column(Boolean)
    n_reversals_so_far = Column(Integer)
    run_id = Column(Integer, ForeignKey("staircase_run.id"), index=True)

    run = relationship("GeometricStaircaseChain", back_populates="nodes")

    def __init__(self, *args, parameter=None, run=None, **kwargs):
        super().__init__(*args, **kwargs)

        if self.network:
            assert self.network.chain_type == "within"

        parent = self.parent
        self.parameter = parameter if parameter is not None else parent.parameter
        self.run = run if run is not None else parent.run
        self.reversal = False

        if self.degree == 0:
            self.n_consecutive_correct = 0
            self.n_reversals_so_far = 0
        else:
            self.n_consecutive_correct = parent.n_consecutive_correct
            self.n_reversals_so_far = parent.n_reversals_so_far

            if parent.trial.score == 1:
                self.n_consecutive_correct += 1

                if self.n_consecutive_correct == self.k:
                    self.increase_difficulty()
                    self.n_consecutive_correct = 0
                    self.reversal = True
                    self.n_reversals_so_far += 1

            elif parent.trial.score == 0:
                self.decrease_difficulty()
                self.n_consecutive_correct = 0
                self.reversal = True
                self.n_reversals_so_far += 1

            else:
                raise ValueError(f"Unexpected score: {parent.trial.score}")

        if self.n_reversals_so_far == self.run.max_reversals_per_chain:
            self.network.full = True

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
    run_id = Column(Integer, ForeignKey("staircase_run.id"), index=True)
    run = relationship(
        "GeometricStaircaseChain", back_populates="all_trials", post_update=True
    )

    parameter = Column(PythonObject)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.run = self.node.run
        self.parameter = self.node.parameter

    def make_definition(self, experiment, participant):
        return {"parameter": self.node.parameter}


class GeometricStaircaseChain(ChainNetwork):
    start_parameter = Column(PythonObject)
    max_reversals_per_chain = Column(Integer)
    mean_reversal_score = Column(Float)

    exclude_first_reversal = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_parameter = self.head.parameter
        self.max_reversals_per_chain = self.trial_maker.max_reversals_per_chain

    def compute_score(self):
        self.compute_reversal_score()

        # A possibility for the future:
        # implement more sophisticated scoring using the upndown R package via rpy2

    def compute_reversal_score(self):
        reversals = [node for node in self.alive_nodes if node.reversal]
        if self.exclude_first_reversal:
            reversals = reversals[1:]
        scores = [node.parameter for node in reversals]
        self.mean_reversal_score = self.summarize_scores(scores)

    def summarize_scores(self, scores):
        return mean(scores)


class GeometricStaircaseTrialMaker(ChainTrialMaker):
    def default_network_class(self):
        return GeometricStaircaseChain

    def __init__(
        self,
        *,
        id_,
        trial_class: Type[GeometricStaircaseTrial],
        node_class: Type[GeometricStaircaseNode],
        network_class: Type["GeometricStaircaseChain"],
        start_nodes: Union[callable, list],
        max_nodes_per_chain: int,
        max_reversals_per_chain: Optional[int] = None,
        balance_across_chains: bool = False,
        min_passing_score: Optional[float] = None,
        max_passing_score: Optional[float] = None,
        expected_trials_per_participant: Optional[int] = None,
        target_n_participants: Optional[int] = None,
        recruit_mode: str = "n_participants",
        assets=None,
        choose_participant_group: Optional[callable] = None,
        sync_group_type: Optional[str] = None,
    ):
        self.max_reversals_per_chain = max_reversals_per_chain
        self.min_passing_score = min_passing_score
        self.max_passing_score = max_passing_score

        super().__init__(
            id_=id_,
            trial_class=trial_class,
            node_class=node_class,
            network_class=network_class,
            chain_type="within",
            target_n_participants=target_n_participants,
            recruit_mode=recruit_mode,
            start_nodes=start_nodes,
            trials_per_node=1,
            expected_trials_per_participant=expected_trials_per_participant,
            assets=assets,
            choose_participant_group=choose_participant_group,
            sync_group_type=sync_group_type,
            max_nodes_per_chain=max_nodes_per_chain,
            check_performance_at_end=True,
            check_performance_every_trial=False,
            balance_across_chains=balance_across_chains,
        )

    def choose_block_order(self, experiment, participant, blocks):
        return sorted(blocks, key=lambda block: int(block))

    score_method = "mean_reversal_score"

    def performance_check(self, experiment, participant, participant_trials):
        """Should return a dict: {"score": float, "passed": bool}"""
        runs = GeometricStaircaseChain.query.filter_by(
            participant=participant, trial_maker_id=self.id
        ).all()

        for run in runs:
            run.compute_score()

        try:
            run_scores = [getattr(run, self.score_method) for run in runs]
        except AttributeError:
            raise ValueError(f"Unknown score method: {self.score_method}")

        score = self.summarize_scores(run_scores)

        passed = True
        if self.min_passing_score is not None and score < self.min_passing_score:
            passed = False
        if self.max_passing_score is not None and score > self.max_passing_score:
            passed = False

        return {
            "score": score,
            "passed": passed,
            "min_passing_score": self.min_passing_score,
            "max_passing_score": self.max_passing_score,
            "score_method": self.score_method,
            "run_scores": run_scores,
        }

    def summarize_scores(self, scores):
        return mean(scores)
