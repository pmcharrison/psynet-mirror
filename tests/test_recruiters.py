import json
from types import SimpleNamespace

import pytest
from dallinger.prolific import ProlificServiceException

from psynet.recruiters import PsyNetProlificRecruiterMixin


class FakeProlificService:
    def __init__(self, response=None, exception=None):
        self.response = response
        self.exception = exception
        self.calls = []

    def get_participant_submission(self, assignment_id):
        self.calls.append(assignment_id)
        if self.exception:
            raise self.exception
        return self.response


def patch_prolific_service(monkeypatch, service):
    import psynet.experiment

    monkeypatch.setattr(
        psynet.experiment,
        "get_experiment",
        lambda: SimpleNamespace(recruiter=SimpleNamespace(prolificservice=service)),
    )


def make_participant(assignment_id="submission-id"):
    return SimpleNamespace(assignment_id=assignment_id, var=SimpleNamespace())


def test_check_assignment_return_status_sets_true_for_returned_submission(monkeypatch):
    service = FakeProlificService(response={"status": "RETURNED"})
    patch_prolific_service(monkeypatch, service)
    participant = make_participant()

    returned = PsyNetProlificRecruiterMixin.check_assignment_return_status(participant)

    assert returned is True
    assert participant.var.assignment_returned is True
    assert participant.var.assignment_return_unverifiable is False
    assert service.calls == ["submission-id"]


def test_check_assignment_return_status_sets_false_for_active_submission(monkeypatch):
    service = FakeProlificService(response={"status": "ACTIVE"})
    patch_prolific_service(monkeypatch, service)
    participant = make_participant()

    returned = PsyNetProlificRecruiterMixin.check_assignment_return_status(participant)

    assert returned is False
    assert participant.var.assignment_returned is False
    assert participant.var.assignment_return_unverifiable is False
    assert service.calls == ["submission-id"]


def test_check_assignment_return_status_marks_missing_submission_unverifiable(
    monkeypatch,
):
    service = FakeProlificService(
        exception=ProlificServiceException(
            json.dumps({"response": {"error": "Not found."}})
        )
    )
    patch_prolific_service(monkeypatch, service)
    participant = make_participant("0shuj912lqi")

    returned = PsyNetProlificRecruiterMixin.check_assignment_return_status(participant)

    assert returned is False
    assert participant.var.assignment_returned is False
    assert participant.var.assignment_return_unverifiable is True
    assert service.calls == ["0shuj912lqi"]


def test_check_assignment_return_status_reraises_other_prolific_errors(monkeypatch):
    service = FakeProlificService(
        exception=ProlificServiceException(
            json.dumps({"response": {"error": "Authentication failed."}})
        )
    )
    patch_prolific_service(monkeypatch, service)
    participant = make_participant()

    with pytest.raises(ProlificServiceException):
        PsyNetProlificRecruiterMixin.check_assignment_return_status(participant)
