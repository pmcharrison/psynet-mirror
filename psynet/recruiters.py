import os
import re

import dallinger.recruiters
import dominate
import flask
import requests
from dallinger.db import session

from .utils import get_logger

logger = get_logger()


class PsyNetRecruiter(dallinger.recruiters.CLIRecruiter):
    """
    The PsyNetRecruiter base class
    """

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

    def recruit(self, n=1):
        """Incremental recruitment isn't implemented for now, so we return an empty list."""
        return []


class BaseCapRecruiter(PsyNetRecruiter):
    """
    The CapRecruiter base class
    """

    def open_recruitment(self, n=1):
        """
        Return an empty list which otherwise would be a list of recruitment URLs.
        """
        return {"items": [], "message": ""}

    def close_recruitment(self):
        logger.info("No more participants required. Recruitment stopped.")

    def reward_bonus(self, participant, amount, reason):
        """
        Return values for `basePay` and `bonus` to cap-recruiter application.
        """
        data = {
            "assignmentId": participant.assignment_id,
            "basePayment": self.config.get("base_payment"),
            "bonus": amount,
            "failed_reason": participant.failure_tags,
        }
        url = self.external_submission_url
        url += "/fail" if participant.failed else "/complete"

        requests.post(
            url,
            json=data,
            headers={"Authorization": os.environ.get("CAP_RECRUITER_AUTH_TOKEN")},
            verify=False,  # Temporary fix because of SSLCertVerificationError
        )


class CapRecruiter(BaseCapRecruiter):

    """
    The production cap-recruiter.

    """

    nickname = "cap-recruiter"
    external_submission_url = "https://cap-recruiter.ae.mpg.de/tasks"


class StagingCapRecruiter(BaseCapRecruiter):

    """
    The staging cap-recruiter.

    """

    nickname = "staging-cap-recruiter"
    external_submission_url = "https://staging-cap-recruiter.ae.mpg.de/tasks"


class DevCapRecruiter(BaseCapRecruiter):

    """
    The development cap-recruiter.

    """

    nickname = "dev-cap-recruiter"
    external_submission_url = "http://localhost:8000/tasks"


class GenericRecruiter(PsyNetRecruiter):
    """
    An improved version of Dallinger's Hot-Air Recruiter.
    """

    nickname = "generic"

    def exit_response(self, experiment, participant):
        from psynet.timeline import Page

        message = experiment.render_exit_message(participant)

        if message is None:
            raise ValueError(
                "experiment.render_exit_message returned None. Did you forget to use 'return'?"
            )

        elif isinstance(message, Page):
            raise ValueError(
                "Sorry, you can't return a Page from experiment.render_exit_message."
            )

        elif message == "default_exit_message":
            return super().exit_response(experiment, participant)

        elif isinstance(message, str):
            html = dominate.tags.p(message).render()

        elif isinstance(message, dominate.dom_tag.dom_tag):
            html = message.render()

        else:
            raise ValueError(
                f"Invalid value of experiment.render_exit_message: {message}. "
                "You should return either a string or an HTML specification created using dominate tags "
                "(see https://pypi.org/project/dominate/)."
            )

        return flask.render_template("custom_html.html", html=html)

    def open_recruitment(self, n=1):
        res = super().open_recruitment(n=n)

        # Hide the Dallinger logs advice, because the advice doesn't work for SSH deployment
        res["message"] = re.sub(
            "Open the logs for this experiment.*", "", res["message"]
        )
        res["message"] = re.sub(
            ".*in the logs for subsequent recruitment URLs\\.", "", res["message"]
        )

        return res
