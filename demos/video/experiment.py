from datetime import datetime
import flask
from urllib.parse import splitquery

import psynet.experiment
from psynet.media import prepare_s3_bucket_for_presigned_urls
from psynet.modular_page import ModularPage, VideoPrompt, VideoRecordControl
from psynet.page import SuccessfulEndPage, UnsuccessfulEndPage
from psynet.timeline import PageMaker, PreDeployRoutine, Timeline, conditional, join
from psynet.utils import get_logger

logger = get_logger()


bucket_name = "video-screen-recording-dev"

video_record_page = join(
    PreDeployRoutine(
        "prepare_s3_bucket_for_presigned_urls",
        prepare_s3_bucket_for_presigned_urls,
        {"bucket_name": bucket_name, "public_read": True, "create_new_bucket": True},
    ),
    ModularPage(
        "video_record_page",
        "This page lets you record video and sound from camera and microphone.",
        VideoRecordControl(
            s3_bucket=bucket_name,
            duration=5.0,
            recording_source='both',
            public_read=True,
            start_delay=5.0,
        ),
        time_estimate=5,
    ),
    conditional(
        "video_record_page",
        lambda experiment, participant: (participant.answer["cameraUrl"] is None and participant.answer["screenUrl"] is None),
        UnsuccessfulEndPage(failure_tags=["video_record_page"])
    ),
    PageMaker(
        lambda participant: ModularPage(
            "video_playback",
            VideoPrompt(
                participant.answer["cameraUrl"],
                flask.Markup(
                    f"""
                        Here's the camera recording you just made.
                        <br>
                        Click <a href="{participant.answer["screenUrl"]}">this link</a> to download the corresponding screen recording.
                    """
                ),
                width="400px",
            ),
        ),
        time_estimate=5,
    ),
    ModularPage(
        "screen_record_page",
        "This page lets you record a video of your screen.",
        VideoRecordControl(
            s3_bucket=bucket_name,
            duration=5.0,
            recording_source='screen',
            record_audio=False,
            public_read=True,
            start_delay=5.0,
        ),
        time_estimate=5,
    ),
    conditional(
        "screen_record_page",
        lambda experiment, participant: participant.answer["screenUrl"] is None,
        UnsuccessfulEndPage(failure_tags=["screen_record_page"])
    ),
    PageMaker(
        lambda participant: ModularPage(
            "screen_playback",
            VideoPrompt(
                participant.answer["screenUrl"],
                "Here's the screen recording you just made.",
                width="400px",
            ),
        ),
        time_estimate=5,
    ),
)


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(video_record_page, SuccessfulEndPage())


extra_routes = Exp().extra_routes()
