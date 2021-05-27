import flask

import psynet.experiment
from psynet.media import prepare_s3_bucket_for_presigned_urls
from psynet.modular_page import ModularPage, VideoPrompt, VideoRecordControl
from psynet.page import SuccessfulEndPage, UnsuccessfulEndPage
from psynet.timeline import (
    Event,
    MediaSpec,
    PageMaker,
    PreDeployRoutine,
    ProgressDisplay,
    Timeline,
    conditional,
    join,
)
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
        "simple_video_prompt",
        VideoPrompt(
            "/static/flower.mp4",
            flask.Markup(
                """
            <h3>Example video prompt:</h3>
            <p><a href="https://commons.wikimedia.org/wiki/File:Water_lily_opening_bloom_20fps.ogv">SecretDisc</a>, <a href="https://creativecommons.org/licenses/by-sa/3.0">CC BY-SA 3.0</a>, via Wikimedia Commons</p>
            """
            ),
        ),
        time_estimate=5,
    ),
    ModularPage(
        "video_play_window",
        VideoPrompt(
            "/static/flower.mp4",
            flask.Markup(
                """
            <h3>Example video prompt with play window:</h3>
            <p><a href="https://commons.wikimedia.org/wiki/File:Water_lily_opening_bloom_20fps.ogv">SecretDisc</a>, <a href="https://creativecommons.org/licenses/by-sa/3.0">CC BY-SA 3.0</a>, via Wikimedia Commons</p>
            """
            ),
            play_window=[3, 4],
        ),
        time_estimate=5,
    ),
    ModularPage(
        "video_plus_audio",
        VideoPrompt(
            "/static/birds.mp4",
            "Here we play a video, muted, alongside an audio file.",
            muted=True,
        ),
        time_estimate=5,
        media=MediaSpec(audio={"soundtrack": "/static/funk-game-loop.mp3"}),
        events={
            "playSoundtrack": Event(
                is_triggered_by="promptStart",
                delay=0.0,
                js="psynet.audio.soundtrack.play()",
            )
        },
    ),
    ModularPage(
        "video_record_page",
        "This page lets you record video and sound from camera and microphone while also doing a simultaneous screen recording.",
        VideoRecordControl(
            s3_bucket=bucket_name,
            duration=5.0,
            recording_source="both",
            public_read=True,
            show_preview=True,
            controls=True,
        ),
        time_estimate=5,
        progress_display=ProgressDisplay(duration=5.0),
    ),
    conditional(
        "video_record_page",
        lambda experiment, participant: (
            participant.answer["camera_url"] is None
            or participant.answer["screen_url"] is None
        ),
        UnsuccessfulEndPage(failure_tags=["video_record_page"]),
    ),
    PageMaker(
        lambda participant: ModularPage(
            "video_playback",
            VideoPrompt(
                participant.answer["camera_url"],
                flask.Markup(
                    f"""
                        Here's the camera recording you just made.
                        <br>
                        Click <a href="{participant.answer["screen_url"]}">this link</a> to download the corresponding screen recording.
                    """
                ),
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
