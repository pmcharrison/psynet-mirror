from datetime import datetime

import psynet.experiment
from psynet.media import prepare_s3_bucket_for_presigned_urls
from psynet.modular_page import ModularPage, VideoPrompt, VideoRecordControl
from psynet.page import SuccessfulEndPage
from psynet.timeline import PageMaker, PreDeployRoutine, Timeline, join
from psynet.utils import get_logger

logger = get_logger()


bucket_name = "video-recording-test3"

video_record_page = join(
    PreDeployRoutine(
        "prepare_s3_bucket_for_presigned_urls",
        prepare_s3_bucket_for_presigned_urls,
        {"bucket_name": bucket_name, "public_read": True, "create_new_bucket": True},
    ),
    ModularPage(
        "video_record_page",
        "This page lets you record from your camera.",
        VideoRecordControl(
            s3_bucket=bucket_name,
            duration=10.0,
            show_meter=False,
            public_read=True,
        ),
        time_estimate=5,
    ),
    # PageMaker(
    #     lambda participant: ModularPage(
    #         "video_playback",
    #         VideoPrompt(
    #             participant.answer["url"], "Here's the video recording you just made. Press the play button to start it!"
    #         ),
    #     ),
    #     time_estimate=5,
    # ),
    ModularPage(
        "screen_record_page",
        "This page lets you record video of your screen.",
        VideoRecordControl(
            s3_bucket=bucket_name,
            duration=10.0,
            record_video=False,
            record_screen=True,
            record_audio=False,
            show_meter=False,
            public_read=True,
        ),
        time_estimate=5,
    ),
    # PageMaker(
    #     lambda participant: ModularPage(
    #         "screen_playback",
    #         VideoPrompt(
    #             participant.answer["url"], "Here's the screen recording you just made."
    #         ),
    #     ),
    #     time_estimate=5,
    # ),
)


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(video_record_page, SuccessfulEndPage())


extra_routes = Exp().extra_routes()
