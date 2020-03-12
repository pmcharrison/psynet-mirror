# pylint: disable=attribute-defined-outside-init

from dallinger.models import Participant
from . import field
import json
import os

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

import rpdb

class UndefinedVariableError(Exception):
    pass

class VarStore:
    def __init__(self, participant):
        self._participant = participant

    def __getattr__(self, name):
        participant = self.__dict__["_participant"]
        if name is "_participant":
            return participant
        else:
            try:
                return participant.details[name]
            except KeyError:
                raise UndefinedVariableError(f"Undefined variable: {name}.")

    def __setattr__(self, name, value):
        if name is "_participant":
            self.__dict__["_participant"] = value
        else:
            # We need to copy the dictionary otherwise
            # SQLAlchemy won't notice that we changed it.
            all_vars = self.__dict__["_participant"].details.copy()
            all_vars[name] = value
            self.__dict__["_participant"].details = all_vars

class TimeCreditStore:
    fields = [
        "confirmed_credit",
        "is_fixed", 
        "pending_credit", 
        "max_pending_credit", 
        "wage_per_hour",
        "experiment_max_time_credit",
        "experiment_max_bonus"
    ]

    def __init__(self, participant):
        self.participant = participant

    def get_internal_name(self, name):
        if name not in self.fields:
            raise ValueError(f"{name} is not a valid field for TimeCreditStore.")
        return f"_time_credit__{name}"

    def __getattr__(self, name):
        if name is "participant":
            return self.__dict__["participant"]
        else:
            return self.participant.get_var(self.get_internal_name(name))

    def __setattr__(self, name, value):
        if name is "participant":
            self.__dict__["participant"] = value
        else:
            self.participant.set_var(self.get_internal_name(name), value)

    def initialise(self, experiment):
        self.confirmed_credit = 0.0
        self.is_fixed = False
        self.pending_credit = 0.0
        self.max_pending_credit = 0.0
        self.wage_per_hour = experiment.wage_per_hour

        experiment_estimated_time_credit = experiment.timeline.estimate_time_credit()
        self.experiment_max_time_credit = experiment_estimated_time_credit.get_max(mode="time")
        self.experiment_max_bonus = experiment_estimated_time_credit.get_max(mode="bonus", wage_per_hour=experiment.wage_per_hour)
        self.export_estimated_payments(experiment_estimated_time_credit, experiment)
    
    def export_estimated_payments(self, experiment_estimated_time_credit, experiment, path="experiment-estimated-payments.json"):
        with open(path, "w+") as file:
            summary = experiment_estimated_time_credit.summarise(
                mode="all", 
                wage_per_hour=experiment.wage_per_hour
            )
            json.dump(summary, file, indent=4)
        logger.info("Exported estimated payment summary to %s.", os.path.abspath(path))

    def increment(self, value: float):
        if self.is_fixed:
            self.pending_credit += value
            if self.pending_credit > self.max_pending_credit:
                self.pending_credit = self.max_pending_credit
        else:
            self.confirmed_credit += value
    
    def start_fix_time(self, time_allotted: float):
        assert not self.is_fixed
        self.is_fixed = True
        self.pending_credit = 0.0
        self.max_pending_credit = time_allotted

    def end_fix_time(self, time_allotted: float):
        assert self.is_fixed
        self.is_fixed = False
        self.pending_credit = 0.0
        self.max_pending_credit = 0.0
        self.confirmed_credit += time_allotted

    def get_bonus(self):
        return self.wage_per_hour * self.confirmed_credit / (60 * 60)

    def estimate_time_credit(self):
        return self.confirmed_credit + self.pending_credit

    def estimate_bonus(self):
        return self.wage_per_hour * self.estimate_time_credit() / (60 * 60)

    def estimate_progress(self):
        return self.estimate_time_credit() / self.experiment_max_time_credit

@property
def var(self):
    return VarStore(self)

@property
def time_credit(self):
    return TimeCreditStore(self)

@property 
def initialised(self):
    return self.elt_id is not None

def _get_var(self, name):
    return self.var.__getattr__(name)

def _set_var(self, name, value):
    self.var.__setattr__(name, value)
    return self

def _set_answer(self, value):
    self.answer = value
    return self

def _initialise(self, experiment):
    self.elt_id = -1
    self.complete = False
    self.time_credit.initialise(experiment)

def _estimate_progress(self):
    return 1.0 if self.complete else self.time_credit.estimate_progress()

def _append_branch_log(self, entry: str):
    # We need to create a new list otherwise the change may not be recognised
    # by SQLAlchemy(?)
    if not isinstance(entry, list) or len(entry) != 2 or not isinstance(entry[0], str):
        raise ValueError(f"Log entry must be a list of length 2 where the first element is a string (received {entry}).")
    if json.loads(json.dumps(entry)) != entry:
        raise ValueError(
            f"The provided log entry cannot be accurately serialised to JSON (received {entry}). " +
            "Please simplify the log entry (this is typically determined by the output type of the user-provided function " +
            "in switch() or conditional())."
        )
    self.branch_log = self.branch_log + [entry]

# @property 
# def estimated_time_credit(self):
#     return self.time_credit.confirmed_credit + self.time_credit.pending_credit

Participant.time_credit = time_credit
Participant.estimate_progress = _estimate_progress
Participant.var = var
Participant.get_var = _get_var
Participant.set_var = _set_var
Participant.set_answer = _set_answer

Participant.elt_id = field.claim_field(1, int)
Participant.page_uuid = field.claim_field(2, str)
Participant.complete = field.claim_field(3, bool)
Participant.answer = field.claim_field(4, object)
Participant.branch_log = field.claim_field(5, list)

Participant.append_branch_log = _append_branch_log
Participant.initialised = initialised
Participant.initialise = _initialise

def get_participant(participant_id):
    return Participant.query.get(participant_id)
