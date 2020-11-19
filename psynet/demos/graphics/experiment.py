# pylint: disable=unused-import,abstract-method,unused-argument,no-member

##########################################################################################
#### Imports
##########################################################################################

from flask import Markup
import psynet.experiment

from psynet.timeline import (
    Timeline, MediaSpec
)
from psynet.page import SuccessfulEndPage, InfoPage, DebugResponsePage
from psynet.modular_page import ModularPage, Prompt, NullControl, AudioRecordControl, AudioMeterControl
from psynet.graphics import (
    GraphicControl,
    GraphicPrompt,
    Frame,
    Image,
    Text,
    Animation,
    Ellipse,
    Rectangle,
    Circle,
    Path
)


##########################################################################################
#### Experiment
##########################################################################################

# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        InfoPage(
            "Graphic components provide a way to display interactive visual animations to the participant.",
            time_estimate=5
        ),
        ModularPage(
            "graphic",
            prompt=GraphicPrompt(
                text="This GraphicPrompt illustrates some of the different kinds of geometric objects.",
                dimensions=[100, 100],
                viewport_width=0.5,
                frames=[
                    Frame(
                        [
                            Path("triangle", "M50,10 L10,50 L90,50 z", attributes={"fill": "red"}),
                            Circle("circle", 20, 70, radius=5, attributes={"fill": "blue"},
                                   animations=[Animation({"cx": 80}, duration=0.7, easing="bounce"),
                                               Animation({"cx": 20}, duration=1.2, easing="ease-out")],
                                   loop_animations=True),
                            Ellipse("ellipse", 80, 80, radius_x=10, radius_y=5, attributes={"fill": "yellow"}),
                            Rectangle("rectangle", 50, 85, width=80, height=5, attributes={"fill": "black"})
                        ]
                    )
                ]
            ),
            time_estimate=5
        ),
        ModularPage(
            "graphic",
            prompt=Prompt(
                text="This is an example of a GraphicControl. Click on one of the objects to continue to the next page.",
            ),
            control=GraphicControl(
                dimensions=[100, 100],
                viewport_width=0.5,
                frames=[
                    Frame(
                        [
                            Text("title", "PsyNet is great!", x=50, y=20,
                                 click_to_answer=True,
                                 persist=True,
                                 attributes={"fill": "blue"},
                                 animations=[Animation({"fill": "red"}, duration=0.2), Animation({"fill": "blue"}, duration=0.2)],
                                 loop_animations=True),
                            Image("logo", media_id="logo", x=10, y=40, width=75, click_to_answer=True,
                                  animations=[
                                      Animation({"x": 5, "y": 45, "width": 60}, duration=0.25),
                                      Animation({"x": 15, "y": 50, "width": 90}, duration=0.25),
                                      Animation({"x": 5, "y": 55, "width": 60}, duration=0.25),
                                      Animation({"x": 10, "y": 60, "width": 76}, duration=0.25)
                                  ])
                        ], duration=1
                    ),
                    Frame(
                        [
                            Image("logo", media_id="logo", x=10, y=60, width=75, click_to_answer=True,
                                  animations=[
                                      Animation({"y": 40, "transform": "r180"}, duration=0.5),
                                      Animation({"y": 40, "transform": "r0"}, duration=0.5)
                                  ])
                        ], duration=1
                    )
                ],
                loop=True,
                media=MediaSpec(image=dict(logo="/static/images/logo.svg"))
            ),
            time_estimate=5
        ),
        DebugResponsePage(),
        ModularPage(
            "audio",
            prompt=GraphicPrompt(
                text="This GraphicPrompt has synchronized audio.",
                dimensions=[100, 100],
                viewport_width=0.5,
                frames=[
                    Frame(
                        [Text("title", "Beer!", x=50, y=30, attributes={"fill": "blue"})],
                        duration=1,
                        audio_id="bier"
                    ),
                    Frame(
                        [Text("title", "Beer!", x=50, y=60, attributes={"fill": "red"})],
                        duration=1,
                        audio_id="bier"
                    ),
                ],
                loop=True,
                media=MediaSpec(audio={"bier": "/static/audio/bier.wav"})
            ),
            time_estimate=5
        ),
        ModularPage(
            "graphic",
            prompt=GraphicPrompt(
                text="This GraphicPrompt illustrates different font sizes.",
                dimensions=[300, 100],
                viewport_width=0.6,
                frames=[Frame([
                    Text("big", "Big text", x=150, y=30, attributes={"font-size": 30}),
                    Text("small", "Small text", x=150, y=70, attributes={"font-size": 10})
                ])]
            ),
            time_estimate=5
        ),
        ModularPage(
            "graphic",
            prompt=GraphicPrompt(
                text="This page contains both a GraphicPrompt and a GraphicControl.",
                dimensions=[300, 100],
                viewport_width=0.6,
                frames=[Frame([
                    Text("question", "What's up? Click to answer.", x=150, y=50)
                ])]
            ),
            control=GraphicControl(
                dimensions=[300, 100],
                viewport_width=0.6,
                frames=[
                    Frame([
                        Text("not_much", "Not much.", x=150, y=20, click_to_answer=True),
                        Text("lots", "Lots.", x=150, y=80, click_to_answer=True)
                    ])
                ]
            ),
            time_estimate=5
        ),
        DebugResponsePage(),
        ModularPage(
            "audio_meter",
            """
            We will now demonstrate audio recording coupled with a Graphic Prompt.
            First we need to enable your sound recorder.
            """,
            AudioMeterControl(calibrate=False),
            time_estimate=5,
        ),
        ModularPage(
            "audio_record",
            prompt=GraphicPrompt(
                text="This example shows how the GraphicPrompt can be used to trigger timing in the Control object.",
                dimensions=[100, 100],
                viewport_width=0.4,
                frames=[
                    Frame([Text("num_3", "3", 50, 50)], duration=1),
                    Frame([Text("num_2", "2", 50, 50)], duration=1),
                    Frame([Text("num_1", "1", 50, 50)], duration=1),
                    Frame([Text("sing", "Sing!", 50, 50)], duration=2, activate_control_response=True),
                    Frame([Text("stop", "Stop.", 50, 50)], duration=None),
                ], prevent_control_response=True
            ),
            control=AudioRecordControl(duration=2, s3_bucket="audio-record-demo"),
            time_estimate=6
        ),
        SuccessfulEndPage()
    )

extra_routes = Exp().extra_routes()
