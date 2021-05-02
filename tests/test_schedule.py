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
            "isTriggeredBy": [{"eventId": "promptFinish", "delay": 1.0}],
            "triggerCondition": "all",
            "delay": 0,
            "once": True,
        },
        "submitReady": {
            "isTriggeredBy": [{"eventId": "promptFinish", "delay": 2.0}],
            "triggerCondition": "all",
            "delay": 0,
            "once": True,
        },
        "promptStart": {
            "isTriggeredBy": [{"eventId": "trialStart", "delay": 0.0}],
            "triggerCondition": "all",
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
            "isTriggeredBy": [],
            "triggerCondition": "all",
            "delay": 0.0,
            "once": True,
        },
        "submitReady": {
            "isTriggeredBy": [],
            "triggerCondition": "all",
            "delay": 0.0,
            "once": True,
        },
        "audioStart": {
            "isTriggeredBy": [{"eventId": "trialStart", "delay": 0.75}],
            "triggerCondition": "all",
            "delay": 0.0,
            "once": True,
        },
        "recordingStart": {
            "isTriggeredBy": [{"eventId": "trialStart", "delay": 1.0}],
            "triggerCondition": "all",
            "delay": 0.0,
            "once": True,
        },
        "recordingEnd": {
            "isTriggeredBy": [{"eventId": "trialStart", "delay": 2.0}],
            "triggerCondition": "all",
            "delay": 0.0,
            "once": True,
        },
        "trialEnd": {
            "isTriggeredBy": [
                {"eventId": "audioEnd", "delay": 0.0},
                {"eventId": "recordingEnd", "delay": 0.0},
            ],
            "triggerCondition": "all",
            "delay": 0.0,
            "once": True,
        },
    }
