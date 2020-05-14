import os

from flask import Markup
from typing import Union, List

from psynet.page import SliderPage

from colour import hsl_dimensions

def get_template(name):
    assert isinstance(name, str)
    data_path = os.path.join('templates', name)
    with open(data_path, encoding='utf-8') as fp:
        template_str = fp.read()
    return template_str

class ColorSliderPage(SliderPage):
    def __init__(
            self,
            label: str,
            prompt: Union[str, Markup],
            selected_idx: int,
            starting_values: List[int],
            reverse_scale: bool,
            time_estimate=None,
            **kwargs
    ):
        assert selected_idx >= 0 and selected_idx < len(hsl_dimensions)
        self.prompt = prompt
        self.selected_idx = selected_idx
        self.starting_values = starting_values

        not_selected_idxs = list(range(len(hsl_dimensions)))
        not_selected_idxs.remove(selected_idx)
        not_selected_names = [hsl_dimensions[i]["name"] for i in not_selected_idxs]
        not_selected_values = [starting_values[i] for i in not_selected_idxs]
        hidden_inputs = dict(zip(not_selected_names, not_selected_values))
        kwargs['template_arg'] = {
            'hidden_inputs': hidden_inputs,
        }
        super().__init__(
            time_estimate=time_estimate,
            template_str=get_template("colour_slider.html"),
            label=label,
            prompt=prompt,
            start_value=starting_values[selected_idx],
            min_value=hsl_dimensions[selected_idx]["min_value"],
            max_value=hsl_dimensions[selected_idx]["max_value"],
            slider_id=hsl_dimensions[selected_idx]["name"],
            reverse_scale=reverse_scale,
            template_arg={
                'hidden_inputs': hidden_inputs,
                'starting_values': starting_values
            },
            continuous_updates=True
        )

    def metadata(self, **kwargs):
        return {
            "prompt": self.prompt,
            "selected_idx": self.selected_idx,
            "starting_values": self.starting_values
        }