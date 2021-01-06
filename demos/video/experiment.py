from datetime import datetime

import psynet.experiment
from psynet.media import prepare_s3_bucket_for_presigned_urls
from psynet.modular_page import ModularPage, VideoRecordControl  # VideoPrompt,
from psynet.page import SuccessfulEndPage
from psynet.timeline import PreDeployRoutine, Timeline, join  # PageMaker,
from psynet.utils import get_logger

logger = get_logger()


bucket_name = "video-recording-test3"

video_record_page = join(
    PreDeployRoutine(
        "prepare_s3_bucket_for_presigned_urls",
        prepare_s3_bucket_for_presigned_urls,
        {"bucket_name": bucket_name, "public_read": True, "create_new_bucket": True}
    ),
    ModularPage(
        "video_record_page",
        "This page lets you record video.",
        VideoRecordControl(
            duration=10.0,
            s3_bucket=bucket_name,
            show_meter=False,
            public_read=True,
        ),
        time_estimate=5,
    ),
    # PageMaker(
    #     lambda participant: ModularPage(
    #         "playback",
    #         VideoPrompt(participant.answer["url"], "Here's the video recording you just made.")
    #     ),
    #     time_estimate=5
    # )
)


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(video_record_page, SuccessfulEndPage())


extra_routes = Exp().extra_routes()
