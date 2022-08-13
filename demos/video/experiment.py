import flask

import psynet.experiment
from psynet.asset import CachedAsset, DebugStorage
from psynet.consent import NoConsent
from psynet.modular_page import (
    AudioRecordControl,
    ModularPage,
    VideoPrompt,
    VideoRecordControl,
)
from psynet.page import SuccessfulEndPage, wait_while
from psynet.timeline import (
    Event,
    MediaSpec,
    PageMaker,
    ProgressDisplay,
    ProgressStage,
    Timeline,
    join,
)
from psynet.utils import get_logger

logger = get_logger()


# def make_js_fade_string(fade_duration):
#     return "{fade_in: %s, fade_out: %s}" % (fade_duration, fade_duration)


all_assets = join(
    CachedAsset(
        key="flower.mp4",
        input_path="assets/flower.mp4",
    ),
    CachedAsset(
        key="birds.mp4",
        input_path="assets/flower.mp4",
    ),
    CachedAsset(
        key="funk-game-loop.mp3",
        input_path="assets/funk-game-loop.mp3",
    ),
    CachedAsset(
        key="video-sync-test.mp4",
        input_path="assets/video-sync-test.mp4",
    ),
    CachedAsset(
        key="video-sync-test.wav",
        input_path="assets/video-sync-test.wav",
    ),
)


video_pages = join(
    PageMaker(
        lambda assets: ModularPage(
            "simple_video_prompt",
            VideoPrompt(
                assets.get("flower.mp4"),
                flask.Markup(
                    """
                <h3>Example video prompt:</h3>
                <p><a href="https://commons.wikimedia.org/wiki/File:Water_lily_opening_bloom_20fps.ogv">SecretDisc</a>, <a href="https://creativecommons.org/licenses/by-sa/3.0">CC BY-SA 3.0</a>, via Wikimedia Commons</p>
                """
                ),
            ),
        ),
        time_estimate=5,
    ),
    PageMaker(
        lambda assets: ModularPage(
            "video_play_window",
            VideoPrompt(
                assets.get("flower.mp4"),
                flask.Markup(
                    """
                <h3>Example video prompt with play window:</h3>
                <p><a href="https://commons.wikimedia.org/wiki/File:Water_lily_opening_bloom_20fps.ogv">SecretDisc</a>, <a href="https://creativecommons.org/licenses/by-sa/3.0">CC BY-SA 3.0</a>, via Wikimedia Commons</p>
                """
                ),
                play_window=[3, 4],
            ),
        ),
        time_estimate=5,
    ),
    PageMaker(
        lambda assets: ModularPage(
            "video_plus_audio",
            VideoPrompt(
                assets.get("birds.mp4"),
                "Here we play a video, muted, alongside an audio file.",
                muted=True,
            ),
            media=MediaSpec(audio={"soundtrack": assets.get("funk-game-loop.mp3")}),
            events={
                "playSoundtrack": Event(
                    is_triggered_by="promptStart",
                    delay=0.0,
                    js="psynet.audio.soundtrack.play()",
                )
            },
        ),
        time_estimate=5,
    ),
    PageMaker(
        lambda assets: ModularPage(
            "video_plus_audio_2",
            VideoPrompt(
                assets.get("video-sync-test.mp4"),
                """
                Here's a second version, where the video and audio both come from the same original recording.
                If everything is working properly, the video and the audio should be well-synchronized.
                """,
                muted=True,
                play_window=[12, None],
            ),
            media=MediaSpec(
                audio={
                    "soundtrack": assets.get("video-sync-test.wav"),
                    # "soundtrack": "https://psynet.s3.amazonaws.com/tests/video-sync-test.wav"
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
        time_estimate=5,
    ),
    PageMaker(
        lambda assets: ModularPage(
            "video_plus_video_record",
            VideoPrompt(
                assets.get("birds.mp4"),
                "Here we play a video and instruct the user to record an audio response.",
                muted=True,
                play_window=[0, 4],
            ),
            AudioRecordControl(
                controls=True,
                duration=4.0,
            ),
            progress_display=ProgressDisplay(stages=[ProgressStage(time=4)]),
            media=MediaSpec(audio={"soundtrack": assets.get("funk-game-loop.mp3")}),
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
        time_estimate=5,
    ),
    PageMaker(
        lambda assets: ModularPage(
            "video_prompt_plus_video_record",
            VideoPrompt(
                url=assets.get("birds.mp4"),  # TODO - rename this argument as 'video'
                text="""
                Here we play a video and instruct the user to record a video response after a countdown.
                The soundtrack also has a 0.5 second fade-in and fade-out.
                """,
                muted=True,
                play_window=[0, 4],
                width="180px",
            ),
            VideoRecordControl(controls=True, duration=4.0, show_preview=True),
            progress_display=ProgressDisplay(
                stages=[
                    ProgressStage(
                        [0.0, 1.0], "Recording in 3 seconds...", color="grey"
                    ),
                    ProgressStage(
                        [1.0, 2.0], "Recording in 2 seconds...", color="grey"
                    ),
                    ProgressStage(
                        [2.0, 3.0], "Recording in 1 seconds...", color="grey"
                    ),
                    ProgressStage([3.0, 4.0 + 3.0], "Recording!", color="red"),
                ],
            ),
            media=MediaSpec(audio={"soundtrack": assets.get("funk-game-loop.mp3")}),
            events={
                "trialPrepare": Event(is_triggered_by=None),
                "promptStart": Event(is_triggered_by="trialStart", delay=3.0),
                "recordStart": Event(is_triggered_by="trialStart", delay=3.0),
                "playSoundtrack": Event(
                    is_triggered_by="promptStart",
                    delay=0.0,
                    js="psynet.audio.soundtrack.play(fade_in: 0.5, fade_out: 0.5)",
                ),
                "stopSoundtrack": Event(
                    is_triggered_by="promptStart",
                    delay=4.0,
                    js="psynet.audio.soundtrack.stop()",
                ),
            },
        ),
        time_estimate=5,
    ),
    ModularPage(
        "video_record_page",
        "This page lets you record video and sound from camera and microphone while also doing a simultaneous screen recording.",
        VideoRecordControl(
            duration=5.0,
            recording_source="both",
            show_preview=True,
            controls=True,
        ),
        time_estimate=5,
        progress_display=ProgressDisplay([ProgressStage(time=5.0)]),
    ),
    wait_while(
        lambda participant: not (
            participant.assets["video_record_page_camera"].deposited
            and participant.assets["video_record_page_screen"].deposited
        ),
        expected_wait=5.0,
        log_message="Waiting for video recordings to be deposited",
    ),
    PageMaker(
        lambda participant: ModularPage(
            "video_playback",
            VideoPrompt(
                participant.assets["video_record_page_camera"],
                flask.Markup(
                    f"""
                        Here's the camera recording you just made.
                        <br>
                        Click <a href="{participant.assets["video_record_page_screen"].url}">this link</a> to download the corresponding screen recording.
                    """
                ),
                width="400px",
            ),
        ),
        time_estimate=5,
    ),
)


class Exp(psynet.experiment.Experiment):
    label = "Video demo"
    asset_storage = DebugStorage()

    timeline = Timeline(NoConsent(), all_assets, video_pages, SuccessfulEndPage())
