from statistics import mean
from typing import Optional, Type, Union

from dallinger import db
from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .data import SQLBase, SQLMixin
from .field import PythonObject
from .trial.chain import ChainNode, ChainTrial, ChainTrialMaker


class GeometricStaircaseNode(ChainNode):
    # k up 2 down procedure
    k = 2

    n_consecutive_correct = Column(Integer)
    parameter = Column(PythonObject)
    reversal = Column(Boolean)
    run_id = Column(Integer, ForeignKey("staircase_run.id"), index=True)

    run = relationship("GeometricStaircaseRun", back_populates="nodes")

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
        else:
            self.n_consecutive_correct = parent.n_consecutive_correct

            if parent.trial.score == 1:
                self.n_consecutive_correct += 1

                if self.n_consecutive_correct == self.k:
                    self.increase_difficulty()
                    self.n_consecutive_correct = 0
                    self.reversal = True

            elif parent.trial.score == 0:
                self.decrease_difficulty()
                self.n_consecutive_correct = 0
                self.reversal = True

            else:
                raise ValueError(f"Unexpected score: {parent.trial.score}")

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
        "GeometricStaircaseRun", back_populates="all_trials", post_update=True
    )

    parameter = Column(PythonObject)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.run = self.node.run
        self.parameter = self.node.parameter

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
        min_passing_score: Optional[float] = None,
        max_passing_score: Optional[float] = None,
        expected_trials_per_participant: Optional[int] = None,
        target_n_participants: Optional[int] = None,
        recruit_mode: str = "n_participants",
        assets=None,
        choose_participant_group: Optional[callable] = None,
        sync_group_type: Optional[str] = None,
    ):
        self.start_parameter = start_parameter
        self.n_runs = n_runs
        self.max_trials_per_run = max_trials_per_run
        self.max_reversals_per_run = max_reversals_per_run
        self.mix_runs = mix_runs
        self.balance_mixed_runs = balance_mixed_runs
        self.min_passing_score = min_passing_score
        self.max_passing_score = max_passing_score

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

        runs = []

        for id_within_participant in range(self.n_runs):
            run = GeometricStaircaseRun(
                trial_maker_id=self.id,
                participant=participant,
                id_within_participant=id_within_participant,
                start_parameter=parameter,
            )
            db.session.add(run)
            runs.append(run)

        start_nodes = [
            self.node_class(
                parameter=parameter,
                run=run,
                block="default" if self.mix_runs else str(run.id_within_participant),
            )
            for run in runs
        ]

        return start_nodes

    def choose_block_order(self, experiment, participant, blocks):
        return sorted(blocks, key=lambda block: int(block))

    score_method = "mean_reversal_score"

    def performance_check(self, experiment, participant, participant_trials):
        """Should return a dict: {"score": float, "passed": bool}"""
        runs = GeometricStaircaseRun.query.filter_by(
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


class GeometricStaircaseRun(SQLBase, SQLMixin):
    __tablename__ = "staircase_run"
    __extra_vars__ = {}

    # Remove default SQL columns
    failed = None
    failed_reason = None
    time_of_death = None
    property1 = None
    property2 = None
    property3 = None
    property4 = None
    property5 = None

    trial_maker_id = Column(String)
    participant_id = Column(Integer, ForeignKey("participant.id"), index=True)
    id_within_participant = Column(Integer)
    start_parameter = Column(PythonObject)
    mean_reversal_score = Column(Float)

    participant = relationship(
        "psynet.participant.Participant", backref="geometric_staircase_runs"
    )
    nodes = relationship("GeometricStaircaseNode")
    all_trials = relationship("GeometricStaircaseTrial")

    # all_trials = relationship(
    #     "GeometricStaircaseTrial",
    #     secondary="node",
    #     primaryjoin="GeometricStaircaseRun.participant_id == GeometricStaircaseNode.participant_id",
    #     secondaryjoin="GeometricStaircaseNode.id == GeometricStaircaseTrial.node_id",
    #     viewonly=True,
    # )

    exclude_first_reversal = True

    def compute_score(self):
        self.compute_reversal_score()

    def compute_reversal_score(self):
        reversals = [node for node in self.nodes if node.reversal]
        if self.exclude_first_reversal:
            reversals = reversals[1:]
        scores = [node.parameter for node in reversals]
        self.mean_reversal_score = self.summarize_scores(scores)

    def summarize_scores(self, scores):
        return mean(scores)


# To do - implement estimator
# see https://cran.r-project.org/web/packages/upndown/vignettes/upndown_basics.html
# simple version: averaging reversals
# complex version: use the upndown R package via rpy2

# To do - implement graph
