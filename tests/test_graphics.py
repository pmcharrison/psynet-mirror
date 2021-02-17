import pytest

from psynet.graphics import Frame, GraphicObject, GraphicPrompt, Image, Text
from psynet.timeline import MediaSpec


def test_id():
    assert isinstance(GraphicObject("sensible_id"), GraphicObject)

    with pytest.raises(ValueError) as e:
        GraphicObject(3)
    assert str(e.value) == "id_ must be a string"

    with pytest.raises(ValueError) as e:
        GraphicObject("3")
    assert str(e.value) == "id_ must be a valid variable name"


def test_image():
    img = Image("logo", "logo_src", x=50, y=50, width=76, height=25)
    assert img.js_init == [
        "this.raphael = paper.image(psynet.image['logo_src'].url, 50, 50, 76, 25);"
    ]


def test_text():
    text = Text("title", "PsyNet is great!", x=50, y=20)
    assert text.js_init == ["this.raphael = paper.text(50, 20, 'PsyNet is great!');"]


def test_validate_object_ids():
    with pytest.raises(ValueError) as e:
        prompt = GraphicPrompt(
            dimensions=[300, 300],
            frames=[
                Frame(
                    [
                        Text("text", "Text 1", x=150, y=30),
                        Text("text", "Text 2", x=150, y=70),
                    ]
                )
            ],
        )
    assert str(e.value) == "in Graphic prompt, Frame 0, duplicate object ID 'text'"

    with pytest.raises(ValueError) as e:
        prompt = GraphicPrompt(
            dimensions=[300, 300],
            frames=[
                Frame(
                    [
                        Text("text_1", "Text 1", x=150, y=30),
                        Text("text_2", "Text 2", x=150, y=70, persist=True),
                    ]
                ),
                Frame(
                    [
                        Text("text_1", "Text 1", x=150, y=30),
                        Text("text_2", "Text 2", x=150, y=70),
                    ]
                ),
            ],
        )
    assert (
        str(e.value)
        == "in Graphic prompt, Frame 1, tried to override persistent object 'text_2'"
    )


def test_validate_media():
    with pytest.raises(ValueError) as e:
        prompt = GraphicPrompt(
            dimensions=[300, 300], frames=[Frame([Image("image", "img", 5, 5, 10, 10)])]
        )
    assert str(e.value) == "image 'img' was missing from the media collection"

    with pytest.raises(ValueError) as e:
        prompt = GraphicPrompt(
            dimensions=[300, 300],
            frames=[Frame([Image("image", "img", 5, 5, 10, 10)], audio_id="sound")],
            media=MediaSpec(image={"img": "img.png"}),
        )
    assert str(e.value) == "audio 'sound' was missing from the media collection"


def test_validate_prompt():
    with pytest.raises(ValueError) as e:
        prompt = GraphicPrompt(
            dimensions=[300, 300],
            frames=[
                Frame(
                    [
                        Text("text1", "Text 1", x=150, y=30),
                        Text("text2", "Text 2", x=150, y=70),
                    ]
                )
            ],
            prevent_control_response=True,
        )
    assert (
        str(e.value)
        == "if prevent_control_response == True, then at least one frame must have activate_control_response == True"
    )

    with pytest.raises(ValueError) as e:
        prompt = GraphicPrompt(
            dimensions=[300, 300],
            frames=[
                Frame(
                    [
                        Text("text1", "Text 1", x=150, y=30),
                        Text("text2", "Text 2", x=150, y=70),
                    ],
                    activate_control_response=True,
                )
            ],
            prevent_control_submit=True,
        )
    assert (
        str(e.value)
        == "if prevent_control_submit == True, then at least one frame must have activate_control_submit == True"
    )

    prompt = GraphicPrompt(
        dimensions=[300, 300],
        frames=[
            Frame(
                [
                    Text("text1", "Text 1", x=150, y=30),
                    Text("text2", "Text 2", x=150, y=70),
                ],
                activate_control_response=True,
                activate_control_submit=True,
            )
        ],
        prevent_control_response=True,
        prevent_control_submit=True,
    )
    assert isinstance(prompt, GraphicPrompt)


# def test_frame():
#     img_1 = ImageObject("logo", "img_1", x=50, y=50, width=5, height=5)
#     img_2 = ImageObject("logo", "img_2", x=20, y=20, width=5, height=5)
#     frame_1 = GraphicFrame([img_1, img_2])
#     assert frame_1.js == "this.logo = paper.image('img_1', 50, 50, 5, 5);\nthis.logo = paper.image('img_2', 20, 20, 5, 5);\n"
#     frame_2 = GraphicFrame([img_1, img_2], duration=1)
#     assert frame_2.js == "this.logo = paper.image('img_1', 50, 50, 5, 5);\nthis.logo = paper.image('img_2', 20, 20, 5, 5);\nsetTimeout(remove_objects, 1000);"
