from psynet.modular_page import (
    AudioPrompt,
    AudioRecordControl,
    ModularPage,
    TextControl,
)


def test_events_format():
    page = ModularPage(
        "test_page",
        AudioPrompt(
            "my-url.wav",
            "Listen to this",
            response_enable_trigger="promptFinish",  # <--- migrate to ModularPage?
            response_enable_delay=1.0,
            submit_enable_trigger="promptFinish",
            submit_enable_delay=2.0,
        ),
        TextControl(),
    )

    assert page.events == {
        "responseReady": {
            "triggered_by": [{"event_id": "promptFinish", "delay": 1.0}],
            "trigger_condition": "all",
            "delay": 0,
            "once": True,
        },
        "submitReady": {
            "triggered_by": [{"event_id": "promptFinish", "delay": 2.0}],
            "trigger_condition": "all",
            "delay": 0,
            "once": True,
        },
        "promptStart": {
            "triggered_by": [{"event_id": "trialStart", "delay": 0.0}],
            "trigger_condition": "all",
            "delay": 0,
            "once": True,
        },
    }


def test_events_audio_record():
    page = ModularPage(
        "audio_page",
        AudioPrompt(
            "my-url.wav",
            "Listen to this",
            response_enable_trigger=None,  # <--- this should be the new default
            response_enable_delay=0.0,
            submit_enable_trigger=None,
            submit_enable_delay=0.0,
            start_delay=0.75,
        ),
        AudioRecordControl(duration=1, s3_bucket="my-bucket", record_window=[1.0, 2.0]),
    )

    assert page.events == {
        "responseReady": {
            "triggered_by": [],
            "trigger_condition": "all",
            "delay": 0.0,
            "once": True,
        },
        "submitReady": {
            "triggered_by": [],
            "trigger_condition": "all",
            "delay": 0.0,
            "once": True,
        },
        "audioStart": {
            "triggered_by": [{"event_id": "trialStart", "delay": 0.75}],
            "trigger_condition": "all",
            "delay": 0.0,
            "once": True,
        },
        "recordingStart": {
            "triggered_by": [{"event_id": "trialStart", "delay": 1.0}],
            "trigger_condition": "all",
            "delay": 0.0,
            "once": True,
        },
        "recordingEnd": {
            "triggered_by": [{"event_id": "trialStart", "delay": 2.0}],
            "trigger_condition": "all",
            "delay": 0.0,
            "once": True,
        },
        "trialEnd": {
            "triggered_by": [
                {"event_id": "audioEnd", "delay": 0.0},
                {"event_id": "recordingEnd", "delay": 0.0},
            ],
            "trigger_condition": "all",
            "delay": 0.0,
            "once": True,
        },
    }
