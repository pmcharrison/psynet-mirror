from flask import Markup

from psynet.modular_page import(
    ModularPage,
    Control
)

class Colour2AFCControl(Control):
    macro = "colour_2afc"
    external_template = "colour_2afc.html"

    def __init__(self, colours):
        super().__init__()
        self.colours = colours

    @property
    def metadata(self):
        return {
            "colours": self.colours
        }
