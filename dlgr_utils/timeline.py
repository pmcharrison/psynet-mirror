import importlib_resources
import flask

from typing import List, Optional

from .utils import dict_to_js_vars
from . import templates

from dallinger.models import Question
from dallinger.db import Base
from dallinger.models import SharedMixin

from sqlalchemy import ForeignKey
from sqlalchemy import Column, String, Text, Enum, Integer, Boolean, DateTime, Float
from sqlalchemy.orm import relationship

from .participant import Participant
from .field import claim_field

def get_template(name):
    assert isinstance(name, str)
    return importlib_resources.read_text(templates, name)

class Elt:
    def render(self, experiment, participant):
        raise NotImplementedError

class CodeBlock(Elt):
    def __init__(self, function):
        self.function = function

    def execute(self, experiment, participant):
        self.function(experiment=experiment, participant=participant)

class Page(Elt):
    def __init__(
        self,
        template_path: Optional[str] = None,
        template_str: Optional[str] = None, 
        template_arg: dict = {},
        label: str = "untitled",
        js_vars: dict = {}
    ):
        if template_path is None and template_str is None:
            raise ValueError("Must provide either template_path or template_str.")
        if template_path is not None and template_str is not None:
            raise ValueError("Cannot provide both template_path and template_str.")

        if template_path is not None:
            with open(template_path, "r") as file:
                template_str = file.read()

        assert len(label) <= 250
        assert isinstance(template_arg, dict)
        assert isinstance(label, str)

        self.template_str = template_str
        self.template_arg = template_arg
        self.label = label
        self.js_vars = js_vars

    def process_response(self, input, experiment, participant, **kwargs):
        pass

    def validate(self, parsed_response, experiment, participant, **kwargs):
        pass

    def render(self, experiment, participant):
        internal_js_vars = {
            "page_uuid": participant.page_uuid
        }
        all_template_arg = {
            **self.template_arg, 
            "init_js_vars": flask.Markup(dict_to_js_vars({**self.js_vars, **internal_js_vars}))
        }
        return flask.render_template_string(self.template_str, **all_template_arg)

class ReactivePage(Elt):
    def __init__(self, function):
        self.function = function

    def resolve(self, experiment, participant):
        page = self.function(experiment=experiment, participant=participant)
        if not isinstance(page, Page):
            raise TypeError("The ReactivePage function must return an object of class Page.")
        return page

class InfoPage(Page):
    def __init__(self, content, title=None, **kwargs):
        super().__init__(
            template_str=get_template("info-page.html"),
            template_arg={
                "content": "" if content is None else content,
                "title": "" if title is None else title
            },
            **kwargs
        )

class FinalPage(Page):
    def __init__(self, content="Experiment complete, please wait...", title=None, wait_sec=750):
        super().__init__(
            template_str=get_template("final-page.html"),
            template_arg={
                "content": "" if content is None else content,
                "title": "" if title is None else title
            },
            js_vars={"wait_sec": wait_sec}
        )

class Button():
    def __init__(self, id, label, begin_disabled=False):
        self.id = id
        self.label = label
        self.begin_disabled = begin_disabled

class NAFCPage(Page):
    def __init__(
        self,
        label: str,
        prompt: str,
        choices: List[str],
        labels=None,
        arrange_vertically=False,
        min_width="300px"
    ):
        self.prompt = prompt
        self.choices = choices 
        self.labels = choices if labels is None else labels
        
        assert isinstance(self.labels, List)
        assert len(self.choices) == len(self.labels)

        if arrange_vertically:
            raise NotImplementedError

        buttons = [
            Button(id=choice, label=label)
            for choice, label in zip(self.choices, self.labels)
        ]
        super().__init__(
            template_str=get_template("nafc-page.html"),
            label=label,
            template_arg={
                "prompt": prompt,
                "buttons": buttons
            }
        )

    def process_response(self, input, metadata, experiment, participant, **kwargs):
        resp = Response(
            participant=participant,
            question_label=self.label, 
            answer=input["answer"],
            page_type=type(self).__name__,
            time_taken=metadata["time_taken"],
            details={
                "prompt": self.prompt,
                "choices": self.choices,
                "labels": self.labels
            }
        )
        participant.answer = resp.answer
        experiment.session.add(resp)
        experiment.save()
        return resp

    def validate(self, parsed_response, experiment, participant, **kwargs):
        pass

class Timeline():
    def __init__(self, elts):
        self.elts = elts
        self.check_elts(elts)        

    def check_elts(self, elts):
        assert isinstance(elts, list)
        assert len(elts) > 0
        if not isinstance(elts[-1], FinalPage):
            raise ValueError("The final element in the timeline must be a FinalPage.")

    def __len__(self):
        return len(self.elts)

    def __getitem__(self, key):
        return self.elts[key]

    def get_current_elt(self, experiment, participant, resolve=True):
        n = participant.elt_id 
        N = len(self)
        if n >= N:
            raise ValueError(f"Tried to get element {n + 1} of a timeline with only {N} element(s).")
        else:
            res = self[n]
            if isinstance(res, ReactivePage) and resolve:
                return res.resolve(experiment, participant)
            else:
                return res

    def advance_page(self, experiment, participant):
        finished = False
        while not finished:
            participant.elt_id += 1
            new_elt = self.get_current_elt(experiment, participant, resolve=False)
            if isinstance(new_elt, CodeBlock):
                new_elt.execute(experiment, participant)
            else:
                participant.page_uuid = experiment.make_uuid()
                finished = True

    def process_response(self, input, experiment, participant):
        elt = self.get_current_elt(experiment, participant)
        parsed_response = elt.process_response(
            input=input,
            experiment=experiment,
            participant=participant
        )
        validation = elt.validate(
            parsed_response=parsed_response,
            experiment=experiment,
            participant=participant
        )
        return validation
        
class RejectedResponse:
    def __init__(self, message="Invalid response, please try again."):
        self.message = message

class Response(Question):
    __mapper_args__ = {"polymorphic_identity": "response"}

    answer = claim_field(1)
    time_taken = claim_field(2, float)
    page_type = claim_field(3, str)

    def __init__(self, participant, question_label, answer, page_type, time_taken, details):
        super().__init__(
            participant=participant,
            question=question_label,
            response="",
            number=-1
        )
        self.answer = answer
        self.details = details
        self.time_taken = time_taken
        self.page_type = page_type
