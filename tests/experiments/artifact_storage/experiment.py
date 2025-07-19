import psynet.experiment
from psynet.artifact import S3ArtifactStorage
from psynet.consent import LucidConsent
from psynet.participant import Participant
from psynet.prescreen import AntiphaseHeadphoneTest
from psynet.timeline import (
    Timeline,
)
from psynet.trial import Trial


class Exp(psynet.experiment.Experiment):
    label = "Artifact Storage demo"
    automatic_backups = True

    artifact_storage = S3ArtifactStorage(root="artifacts", bucket_name="psynet-tests")
    config = {
        # **get_mock_lucid_recruiter(
        #     survey_number=65502067, survey_sid="2928c1b9-0a83-4765-8e03-9e0335991371"
        # ),
        # "lucid_api_key": "XXX",
        # "lucid_sha1_hashing_key": "XXX",
        # "recruiter": "devprolific",
        # **get_mock_prolific_recruiter("67c851c18c5ac1564390c9e3")
        "loglevel": 0,
        "loglevel_worker": 0,
    }

    @classmethod
    def get_basic_data(
        cls,
        context=None,
        **kwargs,
    ):
        """
        More complex example supporting multiple sheets
        """
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
