import psynet.experiment
from psynet.artifact import S3ArtifactStorage
from psynet.consent import LucidConsent
from psynet.participant import Participant
from psynet.prescreen import AntiphaseHeadphoneTest
from psynet.timeline import (
    Timeline,
)
from psynet.trial import Trial


def fail():
    raise Exception()


class Exp(psynet.experiment.Experiment):
    label = "Artifact Storage demo"

    # By default, automatic backups only are made when the experiment is deployed
    # (``psynet deploy ...``) not when it is run in debug mode (``psynet debug ...``).
    # However, if we set ``automatic_backups`` to ``True``, backups will be made
    # when the experiment is run in debug mode as well.
    automatic_backups = True

    artifact_storage = S3ArtifactStorage(root="artifacts", bucket_name="psynet-tests")
    config = {
        # These config parameters are for testing the deployments dashboard
        # with mocked recruiter data.
        # **get_mock_lucid_recruiter(
        #     survey_number=65502067, survey_sid="2928c1b9-0a83-4765-8e03-9e0335991371"
        # ),
        # "lucid_api_key": "XXX",
        # "lucid_sha1_hashing_key": "XXX",
        # "recruiter": "devprolific",
        # **get_mock_prolific_recruiter("67c851c18c5ac1564390c9e3")
    }

    @classmethod
    def get_basic_data(
        cls,
        context=None,
        **kwargs,
    ):
        # This function is meant to return the essential data for the experiment.
        return {
            "trial": [
                {
                    "id": trial.id,
                    "answer": str(trial.answer),
                }
                for trial in Trial.query.all()
            ],
            "participant": [
                {
                    "id": participant.id,
                    "answer": str(participant.answer),
                }
                for participant in Participant.query.filter_by().all()
            ],
        }

    timeline = Timeline(
        LucidConsent(),
        AntiphaseHeadphoneTest(),
    )
