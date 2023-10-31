# import pytest

from psynet.modular_page import (  # AudioPrompt,; VideoSliderControl,
    Control,
    ModularPage,
    Prompt,
)

# from importlib import resources


def test_import_templates():
    page_1 = ModularPage("test", Prompt("Hi!"))
    assert page_1.import_external_templates == ""

    class CustomPrompt(Prompt):
        external_template = "my-prompt.html"
        macro = "prompt"

    class CustomControl(Control):
        external_template = "my-control.html"
        macro = "control"

    page_2 = ModularPage("test", CustomPrompt("Hi!"), CustomControl())
    assert (
        page_2.import_external_templates
        == '{% import "my-prompt.html" as custom_prompt with context %} {% import "my-control.html" as custom_control with context %}'
    )


# The following tests have been disabled because they rely on the iterated singing demo,
# but it has proved tricky to maintain compatibility between the tests and the demo.
# Long-term we should rewrite these.

# @pytest.mark.parametrize("experiment_directory", [path_to_demo("singing_iterated")], indirect=True)
# @pytest.mark.usefixtures("in_experiment_directory")
# def test_visualize_audio_prompt(trial):
#     prompt = AudioPrompt("test.url", "This is the prompt.", play_window=[1, 10])
#     assert (
#         prompt.visualize(trial)
#         == '<p>This is the prompt.</p>\n<audio controls="controls" id="visualize-audio-prompt">\n  <source src="test.url#t=1,10">\n</audio>'
#     )
#
#
# @pytest.mark.parametrize("experiment_directory", [path_to_demo("singing_iterated")], indirect=True)
# @pytest.mark.usefixtures("in_experiment_directory")
# def test_visualize_trial(trial):
#     import psynet.media
#
#     psynet.media.upload_to_local_s3(
#         local_path=resources.files("psynet") / "resources/logo.png",
#         bucket_name="s3-bucket",
#         key="key.png",
#         public_read=True,
#         create_new_bucket=True,
#     )
#     trial.origin.target_url = "target_url"
#     trial.answer = {"s3_bucket": "s3-bucket", "key": "key", "url": "url"}
#     assert (
#         trial.visualization_html
#         == '<div id="trial-visualization">\n  <h3>Prompt</h3>\n  <div id="prompt-visualization" style="background-color: white; padding: 10px; margin-top: 10px; margin-bottom: 10px; border-style: solid; border-width: 1px;"><p>Please sing back the melody to the syllable \'Ta\'.</p>\n<audio controls="controls" id="visualize-audio-prompt">\n  <source src="target_url#t=,">\n</audio></div><br>\n  <h3>Response</h3>\n  <div id="response-visualization" style="background-color: white; padding: 10px; margin-top: 10px; margin-bottom: 10px; border-style: solid; border-width: 1px;"><audio controls="controls" id="visualize-audio-response">\n  <source src="url">\n</audio></div>\n</div><div style="border-style: solid; border-width: 1px;">\n  <img src="/static/s3/s3-bucket/key.png" style="max-width: 100%;">\n</div>'
#     )
#
#     trial.answer = 0.5
#     video_slider_page = ModularPage(
#         "video_slider",
#         prompt="This is an example of a video slider page.",
#         control=VideoSliderControl(
#             url="https://psynet.s3.amazonaws.com/video-slider.mp4",
#             file_type="mp4",
#             width="400px",
#             height="400px",
#             reverse_scale=True,
#             directional=False,
#         ),
#         time_estimate=5,
#     )
#
#     assert (
#         video_slider_page.visualize(trial)
#         == '<div id="trial-visualization">\n  <h3>Prompt</h3>\n  <div id="prompt-visualization" style="background-color: white; padding: 10px; margin-top: 10px; margin-bottom: 10px; border-style: solid; border-width: 1px;"><p>This is an example of a video slider page.</p></div><br>\n  <h3>Response</h3>\n  <div id="response-visualization" style="background-color: white; padding: 10px; margin-top: 10px; margin-bottom: 10px; border-style: solid; border-width: 1px;">\n<div>\n  <p>Answer = 0.5</p>\n  <video controls="controls" id="visualize-video-slider" style="max-width: 400px;">\n    <source src="https://psynet.s3.amazonaws.com/video-slider.mp4">\n  </video>\n</div></div>\n</div>'
#     )
