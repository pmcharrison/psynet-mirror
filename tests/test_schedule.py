from psynet.modular_page import (
    AudioPrompt,
    AudioRecordControl,
    ModularPage,
    TextControl,
)


def test_events_default():
    page = ModularPage(
        "test_page",
        AudioPrompt("my-url.wav", "Listen to this"),
        TextControl(),
    )

    assert page.events == {
        "trialStart": {
            "isTriggeredBy": [],
            "triggerCondition": "all",
            "delay": 0.0,
            "once": True,
        },
        "allowSubmit": {
            "isTriggeredBy": [{"eventId": "trialStart", "delay": 0.0}],
            "triggerCondition": "all",
            "delay": 0.0,
            "once": True,
        },
        "audioPromptStart": {
            "isTriggeredBy": [{"eventId": "trialStart", "delay": 0.0}],
            "triggerCondition": "all",
            "delay": 0.0,
            "once": True,
        },
        "audioPromptEnd": {
            "isTriggeredBy": [],
            "triggerCondition": "all",
            "delay": 0.0,
            "once": True,
        },
    }


def test_events_override():
    from psynet.timeline import Event

    page = ModularPage(
        "test_page",
        "Hello!",
        TextControl(),
        events={"allowSubmit": Event(is_triggered_by="Happiness")},
    )

    assert page.events == {
        "trialStart": {
            "isTriggeredBy": [],
            "triggerCondition": "all",
            "delay": 0.0,
            "once": True,
        },
        "allowSubmit": {
            "isTriggeredBy": [{"eventId": "Happiness", "delay": 0.0}],
            "triggerCondition": "all",
            "delay": 0.0,
            "once": True,
        },
    }


def test_events_audio_record():
    page = ModularPage(
        "audio_page",
        AudioPrompt("my-url.wav", "Listen to this"),
        AudioRecordControl(duration=1, s3_bucket="my-bucket"),
    )

    assert page.events == {
        "trialStart": {
            "isTriggeredBy": [],
            "triggerCondition": "all",
            "delay": 0.0,
            "once": True,
        },
        "allowSubmit": {
            "isTriggeredBy": [{"eventId": "audioRecordEnd", "delay": 0.0}],
            "triggerCondition": "all",
            "delay": 0.0,
            "once": True,
        },
        "audioPromptStart": {
            "isTriggeredBy": [{"eventId": "trialStart", "delay": 0.0}],
            "triggerCondition": "all",
            "delay": 0.0,
            "once": True,
        },
        "audioPromptEnd": {
            "isTriggeredBy": [],
            "triggerCondition": "all",
            "delay": 0.0,
            "once": True,
        },
        "audioRecordStart": {
            "isTriggeredBy": [{"eventId": "trialStart", "delay": 0.0}],
            "triggerCondition": "all",
            "delay": 0.0,
            "once": True,
        },
        "audioRecordEnd": {
            "isTriggeredBy": [{"eventId": "audioRecordStart", "delay": 1.0}],
            "triggerCondition": "all",
            "delay": 0.0,
            "once": True,
        },
    }


# def test_audio():
#     from psynet.modular_page import VideoRecordControl
#
#     page = ModularPage(
#         "record_page",
#         AudioPrompt(
#             url="https://headphone-check.s3.amazonaws.com/funk_game_loop.wav",
#             text="""
#                 This page plays audio and records video alongside.
#                 It'll work best if you wear headphones.
#                 The red portion of the progress bar identifies the period when the video
#                 will be recording.
#                 """,
#             play_window=[0, 4.6],
#             fade_in=0.2,
#         ),
#         VideoRecordControl(
#             duration=4.6,
#             s3_bucket="audio-record-demo",
#             recording_source="camera",
#             show_preview=True,
#             show_meter=False,
#             public_read=True,
#             progress_bar=True,
#             controls=True,
#             loop_playback=False,
#         ),
#         time_estimate=5,
#     )
#     breakpoint()
