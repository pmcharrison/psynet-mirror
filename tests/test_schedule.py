from psynet.modular_page import AudioPrompt, ModularPage, TextControl


def test_schedule_format():
    page = ModularPage(
        "test_page",
        AudioPrompt(
            "my-url.wav",
            "Listen to this",
            response_enable_trigger="promptFinish",
            response_enable_delay=1.0,
            submit_enable_trigger="promptFinish",
            submit_enable_delay=2.0,
        ),
        TextControl(),
    )
    assert page.schedule == {
        "responseReady": {
            "triggers": [{"event_id": "promptFinish", "delay": 1.0}],
            "trigger_condition": "all",
            "delay": 0,
        },
        "submitReady": {
            "triggers": [{"event_id": "promptFinish", "delay": 2.0}],
            "trigger_condition": "all",
            "delay": 0,
        },
    }
