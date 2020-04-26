from psynet.modular_page import ModularPage, Prompt, Control

def test_import_templates():
    page_1 = ModularPage("test", Prompt("Hi!"))
    assert page_1.import_external_templates == ""

    class CustomPrompt(Prompt):
        external_template = "my-prompt.html"
        macro = "prompt"

    class CustomControl(Control):
        external_template = "my-control.html"
        macro = "control"

    page_2 = ModularPage(
        "test",
        CustomPrompt("Hi!"),
        CustomControl()
    )
    assert page_2.import_external_templates == '{% import "my-prompt.html" as custom_prompt with context %} {% import "my-control.html" as custom_control with context %}'
