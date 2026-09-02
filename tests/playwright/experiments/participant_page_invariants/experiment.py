"""
Exercises the participant-facing layout primitives that the structural
invariants check: plain prose, option rows, push buttons, and a tall graphic.

The graphic is deliberately large. Before ``GraphicPrompt.max_viewport_height``
existed it grew tall enough to push the Next button underneath the fixed footer,
which is the regression the ``action_not_occluded`` invariant guards against.
"""

# pylint: disable=unused-import,abstract-method,unused-argument,no-member

import psynet.experiment
from psynet.graphics import Circle, Frame, GraphicPrompt, Path
from psynet.modular_page import (
    ModularPage,
    PushButtonControl,
    RadioButtonControl,
)
from psynet.page import InfoPage
from psynet.timeline import Timeline


class Exp(psynet.experiment.Experiment):
    label = "Participant page invariants"

    timeline = Timeline(
        InfoPage(
            "Invariant check: plain information page.",
            time_estimate=1,
        ),
        ModularPage(
            "radio",
            prompt="Invariant check: radio options.",
            control=RadioButtonControl(
                ["alpha", "beta", "gamma"],
                ["Alpha", "Beta", "Gamma"],
                name="letters",
            ),
            time_estimate=1,
        ),
        ModularPage(
            "push",
            prompt="Invariant check: push buttons.",
            control=PushButtonControl(["left", "right"], ["Left", "Right"]),
            time_estimate=1,
        ),
        ModularPage(
            "graphic",
            prompt=GraphicPrompt(
                text="Invariant check: tall graphic.",
                dimensions=[100, 100],
                viewport_width=0.6,
                frames=[
                    Frame(
                        [
                            Path(
                                "triangle",
                                "M50,10 L10,50 L90,50 z",
                                attributes={"fill": "red"},
                            ),
                            Circle(
                                "circle",
                                20,
                                70,
                                radius=5,
                                attributes={"fill": "blue"},
                            ),
                        ]
                    )
                ],
            ),
            time_estimate=1,
        ),
    )
