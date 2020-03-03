import importlib_resources
import flask

from typing import List, Optional, Union

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

import json

def get_template(name):
    assert isinstance(name, str)
    return importlib_resources.read_text(templates, name)

class Elt:
    returns_time_credit = False
    time_allotted = None
    expected_repetitions = None

    def consume(self, experiment, participant):
        raise NotImplementedError

    def render(self, experiment, participant):
        raise NotImplementedError

    def multiply_expected_repetitions(self, factor):
        return self

    def get_position_in_timeline(self, timeline):
        for i, elt in enumerate(timeline):
            if self == elt:
                return i
        raise ValueError("Elt not found in timeline.")

class NullElt(Elt):
    def consume(self, experiment, participant):
        pass

class CodeBlock(Elt):
    def __init__(self, function):
        self.function = function

    def consume(self, experiment, participant):
        self.function(experiment=experiment, participant=participant)

class FixTime(Elt):
    def __init__(self, time_allotted: float):
        self.time_allotted = time_allotted

class BeginFixTime(FixTime):
    def consume(self, experiment, participant):
        participant.time_credit.begin_fix_time(self.time_allotted)

class EndFixTime(FixTime):
    def consume(self, experiment, participant):
        participant.time_credit.end_fix_time(self.time_allotted)

class GoTo(Elt):
    def __init__(self, target):
        self.target = target

    def get_target(self, experiment, participant):
        return self.target

    def consume(self, experiment, participant):
        # We subtract 1 because elt_id will be incremented again when
        # we return to the beginning of the advance page loop.
        target_elt = self.get_target(experiment, participant)
        target_elt_id = target_elt.get_position_in_timeline(experiment.timeline)
        participant.elt_id = target_elt_id - 1

class ReactiveGoTo(Elt):
    def __init__(
        self, 
        function, # function taking experiment, participant and returning a key
        targets # dict of possible target elements
    ):
        self.check_args()
        self.function = function
        self.targets = targets        

    def check_args(self):
        self.check_function()
        self.check_targets()
    
    def check_function(self):
        if not check_function_args(self.function, ("experiment", "participant")):
            raise TypeError("<function> must be a function of the form f(experiment, participant).")

    def check_targets(self):
        try:
            assert isinstance(self.targets, dict)
            for target in self.targets.items():
                assert isinstance(target, Elt)
        except:
            raise TypeError("<targets> must be a dictionary of Elt objects.")

    def get_target(self, experiment, participant):
        val = self.function(experiment=experiment, participant=participant)
        try:
            return self.targets[val]
        except KeyError:
            raise ValueError(
                f"ReactiveGoTo returned {val}, which is not present among the target keys: " +
                f"{list(self.targets)}."
        )

def check_function_args(f, args):
    return (
        callable(f) 
        and f.__code__.co_varnames == tuple(args)
    )

class Page(Elt):
    returns_time_credit = True

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

    def consume(self, experiment, participant):
        participant.page_uuid = experiment.make_uuid()

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
            "init_js_vars": flask.Markup(dict_to_js_vars({**self.js_vars, **internal_js_vars})),
            "progress_bar": self.create_progress_bar(participant),
            "footer": self.create_footer(experiment, participant)
        }
        return flask.render_template_string(self.template_str, **all_template_arg)

    def create_progress_bar(self, participant):
        return ProgressBar(participant.estimate_progress())

    def create_footer(self, experiment, participant):
        return Footer([
                f"Estimated bonus: <strong>&#36;{participant.time_credit.estimate_bonus():.2f}</strong>"
            ],
            escape=False)

    def multiply_expected_repetitions(self, factor: float):
        self.expected_repetitions = self.expected_repetitions * factor
        return self

class ReactivePage(Elt):
    returns_time_credit = True

    def __init__(self, function, time_allotted: float):
        self.function = function
        self.time_allotted = time_allotted
        self.expected_repetitions = 1

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

    def multiply_expected_repetitions(self, factor: float):
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

    def consume(self, experiment, participant):
        super().__init__(experiment, participant)
        self.finalise_participant(experiment, participant)

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
            old_elt = self.get_current_elt(experiment, participant, resolve=False)
            if old_elt.returns_time_credit:
                participant.time_credit.increment(old_elt.time_allotted)

            participant.elt_id += 1

            new_elt = self.get_current_elt(experiment, participant, resolve=False)
            new_elt.consume(experiment, participant)

            if isinstance(new_elt, Page) or isinstance(new_elt, ReactivePage):
                finished = True

            logger.info(f"participant.elt_id = {json.dumps(participant.elt_id)}")
        logger.info(f"participant.conditionals = {json.dumps(participant.conditionals)}")

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

    def estimate_total_time_credit(self):
        return estimate_time_credit(self.elts)

def estimate_time_credit(elts):
    return sum([
        elt.time_allotted * elt.expected_repetitions
        for elt in elts
        if elt.returns_time_credit
    ])
        
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

def check_condition_and_logic(condition, logic):
    if not check_function_args(condition, ("experiment", "participant")):
        raise TypeError("<condition> must be a function of the form f(experiment, participant).")
    assert isinstance(logic, Elt) or is_list_of_elts(logic)
    if isinstance(logic, Elt):
        logic = [logic]
    if len(logic) == 0:
        raise ValueError("<logic> may not be empty.")
    return logic

class StartWhile(ReactiveGoTo):
    def __init__(self, id, condition, end_loop, jump_on_negative=False):
        super().__init__(condition, target=end_loop, jump_on_negative=jump_on_negative)
        self.id = id

class EndWhile(NullElt):
    pass

def while_loop(id, condition, logic, expected_repetitions: int, fix_time_credit=True):
    logic = check_condition_and_logic(condition, logic)
    
    end_while = EndWhile()
    start_while = StartWhile(id, condition, end_while, jump_on_negative=True)

    elts = join(
        start_while,
        multiply_expected_repetitions(logic, expected_repetitions), 
        end_while
    )

    if fix_time_credit:
        time_allotted = estimate_time_credit(logic)
        return fix_time(elts, time_allotted)
    else:
        return elts

def check_branches(branches):
    try:
        assert isinstance(branches, dict)
        for branch_name, branch_elts in branches.items():
            assert isinstance(branch_elts, Elt) or is_list_of_elts(branch_elts)
            if isinstance(branch_elts, Elt):
                branches[branch_name] = [branch_elts]
        return branches
    except AssertionError:
        raise TypeError("<branches> must be a dict of (lists of) Elt objects.")

def switch(id, function, branches, always_give_time_credit=True):
    if not check_function_args(function, ("experiment", "participant")):
        raise TypeError("<function> must be a function of the form f(experiment, participant).")
    branches = check_branches(branches)
   
    all_branch_starts = dict()
    all_elts = []
    final_elt = EndSwitch(id) 

    for branch_name, branch_elts in branches.items():
        branch_start = BeginSwitchBranch(branch_name)
        branch_end = EndSwitchBranch(branch_name, final_elt)
        all_branch_starts[branch_name] = branch_start
        all_elts = all_elts + [branch_start] + branch_elts + [branch_end]

    return [BeginSwitch(id, function, all_branch_starts)] + all_elts + [final_elt]

class BeginSwitch(ReactiveGoTo):
    def __init__(self, id, function, all_branch_starts):
        super().__init__(function, targets=all_branch_starts)
        self.id = id

class EndSwitch(NullElt):
    def __init__(self, id):
        self.id = id

class BeginSwitchBranch(NullElt):
    def __init__(self, name):
        super().__init__()
        self.name = name

class EndSwitchBranch(GoTo):
    def __init__(self, name, final_elt):
        super().__init__(target=final_elt)
        self.name = name

def conditional(id, condition, logic_if_true, logic_if_false=None, always_give_time_credit=True):
    return switch(
        id, 
        function=condition, 
        branches={
            True: logic_if_true,
            False: NullElt() if logic_if_false is None else logic_if_false
        }, 
        always_give_time_credit=always_give_time_credit
    )

class ConditionalElt(Elt):
    def __init__(self, id: str):
        self.id = id

class BeginConditional(ConditionalElt):
    pass
    
class EndConditional(ConditionalElt):
    pass
   
def fix_time(elts, time_allotted):
    return join(
        BeginFixTime(time_allotted),
        elts,
        EndFixTime(time_allotted)
    )

def multiply_expected_repetitions(logic, factor: float):
    assert isinstance(logic, Elt) or is_list_of_elts(logic)
    if isinstance(logic, Elt):
        logic.multiply_expected_repetitions(factor)
    else:
        for elt in logic:
            elt.multiply_expected_repetitions(factor)
    return logic

class ProgressBar():
    def __init__(self, progress: float, show=True):
        self.show = show
        self.percentage = round(progress * 100)
        if self.percentage > 99:
            self.percentage = 99
        elif self.percentage < 1:
            self.percentage = 5

class Footer():
    def __init__(self, text_to_show: List[str], escape=True, show=True):
        self.show = show
        self.text_to_show = [x if escape else flask.Markup(x) for x in text_to_show]
