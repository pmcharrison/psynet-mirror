import os

import dallinger.recruiters
import requests
from dallinger.db import session

from .utils import get_logger

logger = get_logger()


class BaseCapRecruiter(dallinger.recruiters.CLIRecruiter):

    """
    The CapRecruiter base class

    """

    def open_recruitment(self, n=1):
        """
        Return an empty list which otherwise would be a list of recruitment URLs.
        """
        return {"items": [], "message": ""}

    def recruit(self, n=1):
        return []

    def close_recruitment(self):
        logger.info("No more participants required. Recruitment stopped.")

    def compensate_worker(self, *args, **kwargs):
        """A recruiter may provide a means to directly compensate a worker."""
        raise RuntimeError("Compensation is not implemented.")

    def notify_duration_exceeded(self, participants, reference_time):
        """
        The participant has been working longer than the time defined in
        the "duration" config value.
        """
        for participant in participants:
            participant.status = "abandoned"
            session.commit()

    def reward_bonus(self, assignment_id, amount, reason):
        """
        Return values for `basePay` and `bonus` to cap-recruiter application.
        """
        data = {
            "assignmentId": assignment_id,
            "basePayment": self.config.get("base_payment"),
            "bonus": amount,
        }
        requests.post(
            self.external_submission_url,
            json=data,
            headers={"Authorization": os.environ.get("CAP_RECRUITER_AUTH_TOKEN")},
            verify=False,  # Temporary fix because of SSLCertVerificationError
        )


class CapRecruiter(BaseCapRecruiter):

    """
    The production cap-recruiter.

    """

    nickname = "cap-recruiter"
    external_submission_url = "https://cap-recruiter.ae.mpg.de/hits/complete"


class StagingCapRecruiter(BaseCapRecruiter):

    """
    The staging cap-recruiter.

    """

    nickname = "staging-cap-recruiter"
    external_submission_url = "https://staging-cap-recruiter.ae.mpg.de/hits/complete"


class DevCapRecruiter(BaseCapRecruiter):

    """
    The development cap-recruiter.

    """

    nickname = "dev-cap-recruiter"
    external_submission_url = "http://localhost:8000/hits/complete"
