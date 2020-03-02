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

from functools import reduce

import rpdb

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

from .participant import Participant
from .field import claim_field

def get_template(name):
    assert isinstance(name, str)
    return importlib_resources.read_text(templates, name)

class Elt:
    def render(self, experiment, participant):
        raise NotImplementedError

    def multiply_expected_repetitions(self, factor):
        return self

class CodeBlock(Elt):
    def __init__(self, function):
        self.function = function

    def execute(self, experiment, participant):
        self.function(experiment=experiment, participant=participant)

class GoTo(Elt):
    def __init__(self, jump_by: int):
        self.jump_by = jump_by

    def resolve(self, experiment, participant):
        return self.jump_by

class ReactiveGoTo(GoTo):
    def __init__(
        self,  
        jump_by=lambda experiment, particiant: True,
        condition=lambda experiment, participant: True,
        negate: bool = False
    ):
        if not (isinstance(jump_by, int) or check_function_args(jump_by, ("experiment", "participant"))):
            raise TypeError(
                "<jump_by> must either be an integer or a function of the form "
                "f(experiment, participant) that returns an integer."
            )
        if not (isinstance(condition, bool) or check_function_args(condition, ("experiment", "participant"))):
            raise TypeError(
                "<test> must either be an Boolean or a function of the form "
                "f(experiment, participant)."
            )
        self.jump_by = jump_by if callable(jump_by) else lambda experiment, participant: jump_by
        self.condition = condition if callable(condition) else lambda experiment, participant: condition
        self.negate = negate

    def resolve(self, experiment, participant):
        cond = self.condition(experiment, participant)
        if not isinstance(cond, bool):
            raise TypeError("ReactiveGoTo.jump_by must return a Boolean.")
        if cond != self.negate:
            jump_by = self.jump_by(experiment, participant) 
            if not isinstance(jump_by, int):
                raise TypeError("ReactiveGoTo.jump_by must return an integer.")
            return jump_by
        else: 
            return 1

def check_function_args(f, args):
    return (
        callable(f) 
        and f.__code__.co_varnames == tuple(args)
    )

class Page(Elt):
    def __init__(
        self,
        time_allotted: Optional[float] = None,
        template_path: Optional[str] = None,
        template_str: Optional[str] = None, 
        template_arg: dict = {},
        label: str = "untitled",
        js_vars: dict = {},
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

        self.time_allotted = time_allotted
        self.template_str = template_str
        self.template_arg = template_arg
        self.label = label
        self.js_vars = js_vars

        self.expected_repetitions = 1 

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

    def multiply_expected_repetitions(self, factor: float):
        self.expected_repetitions = self.expected_repetitions * factor
        return self

class ReactivePage(Elt):
    def __init__(self, function, time_allotted: float):
        self.function = function
        self.time_allotted = time_allotted

    def resolve(self, experiment, participant):
        page = self.function(experiment=experiment, participant=participant)
        if self.time_allotted != page.time_allotted and page.time_allotted is not None:
            logger.warn(
                f"Observed a mismatch between a reactive page's time_allotted slot ({self.time_allotted}) " +
                f"and the time_allotted slot of the generated page ({page.time_allotted}). " +
                f"The former will take precedent."
            )
        if not isinstance(page, Page):
            raise TypeError("The ReactivePage function must return an object of class Page.")
        return page

    def expected_repetitions(self, factor: float):
        self.expected_repetitions = self.expected_repetitions * factor
        return self

class InfoPage(Page):
    def __init__(self, content, time_allotted=None, title=None, **kwargs):
        super().__init__(
            time_allotted=time_allotted,
            template_str=get_template("info-page.html"),
            template_arg={
                "content": "" if content is None else content,
                "title": "" if title is None else title
            },
            **kwargs
        )

class EndPage(Page):
    def __init__(self, content="Experiment complete, please wait...", title=None, wait_sec=750):
        super().__init__(
            time_allotted=0,
            template_str=get_template("final-page.html"),
            template_arg={
                "content": "" if content is None else content,
                "title": "" if title is None else title
            },
            js_vars={"wait_sec": wait_sec}
        )

    def finalise_participant(self, experiment, participant):
        pass

class SuccessfulEndPage(EndPage):
    def finalise_participant(self, experiment, participant):
        participant.complete = True

class UnsuccessfulEndPage(EndPage):
    pass

class Button():
    def __init__(self, id, label, min_width, begin_disabled=False):
        self.id = id
        self.label = label
        self.min_width = min_width
        self.begin_disabled = begin_disabled

class NAFCPage(Page):
    def __init__(
        self,
        label: str,
        prompt: str,
        choices: List[str],        
        time_allotted=None,
        labels=None,
        arrange_vertically=False,
        min_width="100px"
    ):
        self.prompt = prompt
        self.choices = choices 
        self.labels = choices if labels is None else labels
        
        assert isinstance(self.labels, List)
        assert len(self.choices) == len(self.labels)

        if arrange_vertically:
            raise NotImplementedError

        buttons = [
            Button(id=choice, label=label, min_width=min_width)
            for choice, label in zip(self.choices, self.labels)
        ]
        super().__init__(
            time_allotted=time_allotted,
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
    def __init__(self, *args):
        elts = join(*args)
        self.elts = elts
        self.check_elts(elts)        

    def check_elts(self, elts):
        assert isinstance(elts, list)
        assert len(elts) > 0
        if not isinstance(elts[-1], EndPage):
            raise ValueError("The final element in the timeline must be a EndPage.")
        for i, elt in enumerate(elts):
            if (isinstance(elt, Page) or isinstance(elt, ReactivePage)) and elt.time_allotted is None:
                raise ValueError(f"Element {i} of the timeline was missing a time_allotted value.")

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
            elif isinstance(new_elt, GoTo):
                # We subtract 1 because elt_id will be incremented again when
                # we return to the beginning of this while loop.
                participant.elt_id += new_elt.resolve(experiment, participant) - 1
            else:
                assert isinstance(new_elt, Page) or isinstance(new_elt, ReactivePage)
                finished = True
                participant.page_uuid = experiment.make_uuid()
                if isinstance(new_elt, EndPage):
                    new_elt.finalise_participant(experiment, participant)

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

def is_list_of_elts(x: list):
    for val in x:
        if not isinstance(val, Elt):
            return False
    return True

def join(*args):
    for i, arg in enumerate(args):
        if not (isinstance(arg, Elt) or is_list_of_elts(arg)):
            raise TypeError(f"Element {i + 1} of the input to join() was neither an Elt nor a list of Elts.")        

    if len(args) == 0:
        return []
    elif len(args) == 1 and isinstance(args[0], Elt):
        return [args[0]]
    else:
        def f(x, y):
            if isinstance(x, Elt) and isinstance(y, Elt):
                return [x, y]
            elif isinstance(x, Elt) and isinstance(y, list):
                return [x] + y
            elif isinstance(x, list) and isinstance(y, Elt):
                return x + [y]
            elif isinstance(x, list) and isinstance(y, list):
                return x + y
            else:
                return Exception("An unexpected error occurred.")    

        return reduce(f, args)

def while_loop(condition, logic, expected_repetitions: int):
    if not check_function_args(condition, ("experiment", "participant")):
        raise TypeError("<condition> must be a function of the form f(experiment, participant).")
    assert isinstance(logic, Elt) or is_list_of_elts(logic)
    if isinstance(logic, Elt):
        logic = [logic]
    if len(logic) == 0:
        raise ValueError("<logic> may not be empty.")
    
    return join(
        ReactiveGoTo(jump_by=len(logic) + 2, condition=condition, negate=True),
        multiply_expected_repetitions(logic, expected_repetitions), 
        GoTo(jump_by=-len(logic) - 1)
    )
    
def multiply_expected_repetitions(logic, factor: float):
    assert isinstance(logic, Elt) or is_list_of_elts(logic)
    if isinstance(logic, Elt):
        logic.multiply_expected_repetitions(factor)
    else:
        for elt in logic:
            elt.multiply_expected_repetitions(factor)
    return logic
