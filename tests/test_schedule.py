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
        "allowResponse": {
            "isTriggeredBy": [{"eventId": "trialStart", "delay": 0.0}],
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
