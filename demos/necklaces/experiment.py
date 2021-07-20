# pylint: disable=unused-import,abstract-method,unused-argument,no-member

##########################################################################################
# Imports
##########################################################################################


import psynet.experiment
from psynet.graphics import (
    Animation,
    Circle,
    Ellipse,
    Frame,
    GraphicControl,
    GraphicPrompt,
    Image,
    Path,
    Rectangle,
    Text,
)
from psynet.modular_page import (
    AudioMeterControl,
    AudioRecordControl,
    ModularPage,
    Prompt,
)
from psynet.page import DebugResponsePage, InfoPage, SuccessfulEndPage
from psynet.timeline import MediaSpec, Timeline

from typing import List


class NecklaceCircle(Circle):
    """
    A circle object.

    Parameters
    ----------

    id_
        A unique identifier for the object.

    x
        x coordinate.

    y
        y coordinate.

    radius
        The circle's radius.

    **kwargs
        Additional parameters passed to :class:`~psynet.graphic.GraphicObject`.
    """

    def __init__(
        self,
        id_: str,
        x: int,
        y: int,
        radius: int,
        color_options: List[str],
        initial_color: int,
        interactive: bool,
        **kwargs
    ):
        self.color_options = color_options
        self.initial_color = initial_color
        self.interactive = interactive
        super().__init__(
            id_,
            x,
            y,
            radius,
            click_to_answer=not interactive,
            **kwargs
        )

    @property
    def js_init(self) -> str:
        return [
            *super().js_init,
            f"""
            let initial_color = {self.initial_color};
            let color_options = {self.color_options};
            this.raphael.attr({{"stroke": color_options[initial_color], "fill": color_options[initial_color]}});

            if (psynet.response.staged.raw_answer == undefined) {{
                psynet.response.staged.raw_answer = {{}};
            }}

            let stage_color = function(index, circle_id) {{
                psynet.response.staged.raw_answer[circle_id] = {{
                    color_index: index,
                    color_value: color_options[index]
                }};
            }};

            stage_color(initial_color, "{self.id}");

            this.raphael.click(function () {{
                if ("{self.interactive}" == "True") {{
                    let currentColor = this.attrs.fill;
                    let targetIdx = (color_options.findIndex(element => element == currentColor) + 1) % color_options.length
                    this.attr({{"stroke": color_options[targetIdx], "fill": color_options[targetIdx]}});
                    stage_color(targetIdx, "{self.id}");
                }}
            }});
            """,
        ]


def create_necklace(px, py, size, spacing, coloring, color_options, necklace_id, interactive):
    translation = 0
    necklace = []
    for i in range(len(coloring)):
        necklace = necklace + [
            NecklaceCircle(
                id_=necklace_id + "_circle_" + str(i),
                x=px + translation,
                y=py,
                radius=size,
                color_options=color_options,
                initial_color=coloring[i],
                interactive=interactive
            )
        ]
        translation += spacing
    return necklace
##########################################################################################
# Experiment
##########################################################################################


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        InfoPage(
            "Graphic components provide a way to display interactive visual animations to the participant.",
            time_estimate=5,
        ),
        ModularPage(
            "graphic",
            prompt=GraphicPrompt(
                text="This GraphicPrompt illustrates some of the different kinds of geometric objects.",
                dimensions=[640, 480],
                viewport_width=0.5,
                frames=[
                    Frame(
                        # [
                        #     NecklaceCircle(
                        #         id_="Clickable",
                        #         x=120,
                        #         y=250,
                        #         radius=20,
                        #         color_options=["red", "green", "blue"],
                        #         initial_color=0
                        #     )
                        # ]
                        create_necklace(
                            necklace_id="necklace",
                            px=120,
                            py=250,
                            size=20,
                            spacing=41,
                            coloring=[0, 1, 2, 0, 1, 1],
                            color_options=["red", "green", "blue"],
                            interactive=False
                        )
                    )
                ],
            ),
            time_estimate=5,
        ),
        DebugResponsePage(),
        SuccessfulEndPage(),
    )

test = create_necklace(
    necklace_id="necklace",
    px=120,
    py=250,
    size=20,
    spacing=41,
    coloring=[0, 1, 2, 0, 1, 1],
    color_options=["red", "green", "blue"],
    interactive=True
)