import flask

import psynet.experiment
from psynet.consent import NoConsent
from psynet.media import prepare_s3_bucket_for_presigned_urls
from psynet.modular_page import (
    AudioRecordControl,
    ModularPage,
    VideoPrompt,
    VideoRecordControl,
)
from psynet.page import SuccessfulEndPage, UnsuccessfulEndPage
from psynet.timeline import (
    Event,
    MediaSpec,
    PageMaker,
    PreDeployRoutine,
    ProgressDisplay,
    ProgressStage,
    Timeline,
    conditional,
    join,
)
from psynet.utils import get_logger

logger = get_logger()

bucket_name = "video-screen-recording-dev"


def make_js_fade_string(fade_duration):
    return "{fade_in: %s, fade_out: %s}" % (fade_duration, fade_duration)


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
        "video_plus_audio_2",
        VideoPrompt(
            "https://psynet.s3.amazonaws.com/tests/video-sync-test.webm",
            """
            Here's a second version, where the video and audio both come from the same original recording.
            If everything is working properly, the video and the audio should be well-synchronized.
            """,
            muted=True,
            play_window=[12, None],
        ),
        time_estimate=5,
        media=MediaSpec(
            audio={
                "soundtrack": "https://psynet.s3.amazonaws.com/tests/video-sync-test.wav"
            }
        ),
        events={
            "playSoundtrack": Event(
                is_triggered_by="promptStart",
                delay=0.0,
                js="psynet.audio.soundtrack.play()",
            )
        },
    ),
    ModularPage(
        "video_plus_video_record",
        VideoPrompt(
            "/static/birds.mp4",
            "Here we play a video and instruct the user to record an audio response.",
            muted=True,
            play_window=[0, 4],
        ),
        AudioRecordControl(
            controls=True,
            duration=4.0,
            s3_bucket=bucket_name,
        ),
        time_estimate=5,
        progress_display=ProgressDisplay(duration=4.0),
        media=MediaSpec(audio={"soundtrack": "/static/funk-game-loop.mp3"}),
        events={
            "playSoundtrack": Event(
                is_triggered_by="promptStart",
                delay=0.0,
                js="psynet.audio.soundtrack.play()",
            ),
            "stopSoundtrack": Event(
                is_triggered_by="promptStart",
                delay=4.0,
                js="psynet.audio.soundtrack.stop()",
            ),
        },
    ),
    ModularPage(
        "video_prompt_plus_video_record",
        VideoPrompt(
            url="/static/birds.mp4",
            text="""
            Here we play a video and instruct the user to record a video response after a countdown.
            The soundtrack also has a 0.5 second fade-in and fade-out.
            """,
            muted=True,
            play_window=[0, 4],
            width="180px",
        ),
        VideoRecordControl(
            controls=True, duration=4.0, s3_bucket=bucket_name, show_preview=True
        ),
        time_estimate=5,
        progress_display=ProgressDisplay(
            duration=4.0 + 3.0,  # 4.0 seconds recording, 3.0 seconds delay
            stages=[
                ProgressStage([0.0, 1.0], "Recording in 3 seconds...", color="grey"),
                ProgressStage([1.0, 2.0], "Recording in 2 seconds...", color="grey"),
                ProgressStage([2.0, 3.0], "Recording in 1 seconds...", color="grey"),
                ProgressStage([3.0, 4.0 + 3.0], "Recording!", color="red"),
            ],
        ),
        media=MediaSpec(audio={"soundtrack": "/static/funk-game-loop.mp3"}),
        events={
            "trialPrepare": Event(is_triggered_by=None),
            "promptStart": Event(is_triggered_by="trialStart", delay=3.0),
            "recordStart": Event(is_triggered_by="trialStart", delay=3.0),
            "playSoundtrack": Event(
                is_triggered_by="promptStart",
                delay=0.0,
                js=f"psynet.audio.soundtrack.play({make_js_fade_string(fade_duration=0.5)})",
            ),
            "stopSoundtrack": Event(
                is_triggered_by="promptStart",
                delay=4.0,
                js="psynet.audio.soundtrack.stop()",
            ),
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
    timeline = Timeline(NoConsent(), video_record_page, SuccessfulEndPage())
