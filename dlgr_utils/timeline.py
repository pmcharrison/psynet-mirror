# pylint: disable=abstract-method

import importlib_resources
import flask
import gevent
import time

from flask import Markup

from typing import List, Optional, Dict, Union

from .utils import dict_to_js_vars, call_function, check_function_args
from . import templates

from dallinger.models import Question

from functools import reduce

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

from .field import claim_field

# pylint: disable=unused-import
import rpdb

def get_template(name):
    assert isinstance(name, str)
    return importlib_resources.read_text(templates, name)

class Elt:
    returns_time_credit = False
    time_allotted = None
    expected_repetitions = None
    id = None

    def consume(self, experiment, participant):
        raise NotImplementedError

    def render(self, experiment, participant):
        raise NotImplementedError

    def multiply_expected_repetitions(self, factor):
        # pylint: disable=unused-argument
        return self

    # def get_position_in_timeline(self, timeline):
    #     for i, elt in enumerate(timeline):
    #         if self == elt:
    #             return i
    #     raise ValueError("Elt not found in timeline.")

class NullElt(Elt):
    def consume(self, experiment, participant):
        pass

class CodeBlock(Elt):
    def __init__(self, function):
        self.function = function

    def consume(self, experiment, participant):
        call_function(self.function, {
            "self": self,
            "experiment": experiment,
            "participant": participant
        })

class FixTime(Elt):
    def __init__(self, time_allotted: float):
        self.time_allotted = time_allotted
        self.expected_repetitions = 1

    def multiply_expected_repetitions(self, factor):
        self.expected_repetitions = self.expected_repetitions * factor

class StartFixTime(FixTime):
    def __init__(self, time_allotted, end_fix_time):
        super().__init__(time_allotted)
        self.end_fix_time = end_fix_time

    def consume(self, experiment, participant):
        participant.time_credit.start_fix_time(self.time_allotted)

class EndFixTime(FixTime):
    def consume(self, experiment, participant):
        participant.time_credit.end_fix_time(self.time_allotted)

class GoTo(Elt):
    def __init__(self, target):
        self.target = target

    def get_target(self, experiment, participant):
        # pylint: disable=unused-argument
        return self.target

    def consume(self, experiment, participant):
        # We subtract 1 because elt_id will be incremented again when
        # we return to the startning of the advance page loop.
        target_elt = self.get_target(experiment, participant)
        target_elt_id = target_elt.id
        participant.elt_id = target_elt_id - 1

class ReactiveGoTo(GoTo):
    def __init__(
        self, 
        function, # function taking experiment, participant and returning a key
        targets # dict of possible target elements
    ):  
        # pylint: disable=super-init-not-called
        self.function = function
        self.targets = targets        
        self.check_args()

    def check_args(self):
        self.check_function()
        self.check_targets()
    
    def check_function(self):
        check_function_args(self.function, ("self", "experiment", "participant"), exact=False)

    def check_targets(self):
        try:
            assert isinstance(self.targets, dict)
            for target in self.targets.values():
                assert isinstance(target, Elt)
        except:
            raise TypeError("<targets> must be a dictionary of Elt objects.")

    def get_target(self, experiment, participant):
        val = call_function(
            self.function,
            {
                "self": self,
                "experiment": experiment,
                "participant": participant
            }
        )
        try:
            return self.targets[val]
        except KeyError:
            raise ValueError(
                f"ReactiveGoTo returned {val}, which is not present among the target keys: " +
                f"{list(self.targets)}."
        )

class Page(Elt):
    returns_time_credit = True

    def __init__(
        self,
        time_allotted: Optional[float] = None,
        template_path: Optional[str] = None,
        template_str: Optional[str] = None, 
        template_arg: Optional[Dict] = None,
        label: str = "untitled",
        js_vars: Optional[Dict] = None,
    ):
        if template_arg is None:
            template_arg = {}
        if js_vars is None:
            js_vars = {}

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

    def process_response(self, response, metadata, experiment, participant, **kwargs):
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
        # pylint: disable=unused-argument
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
        # self.pos_in_reactive_seq = None

    def consume(self, experiment, participant):
        participant.page_uuid = experiment.make_uuid()

    def resolve(self, experiment, participant):
        page = call_function(
            self.function,
            {
                "self": self,
                "experiment": experiment,
                "participant": participant
            }
        )
        # page = self.function(experiment=experiment, participant=participant)
        if self.time_allotted != page.time_allotted and page.time_allotted is not None:
            logger.warning(
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

    # def set_pos_in_reactive_seq(self, val):
    #     assert isinstance(val, int)
    #     self.pos_in_reactive_seq = val
    #     return self


def reactive_seq(
    label,
    function, 
    num_pages: int,
    time_allotted: int
): 
    """Function must return a list of pages when evaluated."""
    def with_namespace(x=None):
        prefix = f"__reactive_seq__{label}"
        if x is None:
            return prefix
        return f"{prefix}__{x}"

    def new_function(self, experiment, participant):
        pos = participant.get_var(with_namespace("pos"))
        elts = call_function(
            function,
            {
                "self": self,
                "experiment": experiment,
                "participant": participant
            }
        )
        if isinstance(elts, Elt):
            elts = [elts]
        assert len(elts) == num_pages
        res = elts[pos]
        assert isinstance(res, Page)
        return res

    prepare_logic = CodeBlock(lambda participant: (
        participant
            .set_var(with_namespace("complete"), False)
            .set_var(with_namespace("pos"), 0)
            .set_var(with_namespace("seq_length"), num_pages)
    ))

    update_logic = CodeBlock(
        lambda participant: (
            participant
                .set_var(
                    with_namespace("complete"), 
                    participant.get_var(with_namespace("pos")) >= num_pages - 1
                )
                .inc_var(with_namespace("pos"))
        )   
    )

    show_elts = ReactivePage(
        new_function, 
        time_allotted=time_allotted / num_pages
    )

    condition = lambda participant: not participant.get_var(with_namespace("complete"))

    return join(
        prepare_logic,
        while_loop(
            label=with_namespace(label), 
            condition=condition, 
            logic=[show_elts, update_logic], 
            expected_repetitions=num_pages,
            fix_time_credit=False
        )
    )

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
        super().consume(experiment, participant)
        self.finalise_participant(experiment, participant)

    def finalise_participant(self, experiment, participant):
        pass

class SuccessfulEndPage(EndPage):
    def finalise_participant(self, experiment, participant):
        participant.complete = True

class UnsuccessfulEndPage(EndPage):
    pass

class Button():
    def __init__(self, button_id, label, min_width, start_disabled=False):
        self.id = button_id
        self.label = label
        self.min_width = min_width
        self.start_disabled = start_disabled

class NAFCPage(Page):
    def __init__(
        self,
        label: str,
        prompt: Union[str, Markup],
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
            Button(button_id=choice, label=label, min_width=min_width)
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

    def process_response(self, response, metadata, experiment, participant, **kwargs):
        resp = Response(
            participant=participant,
            question_label=self.label, 
            answer=response["answer"],
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

class TextInputPage(Page):
    def __init__(
        self,
        label: str,
        prompt: Union[str, Markup],     
        time_allotted=None,
        one_line=True,
        width=None, # e.g. "100px"
        height=None
    ):
        self.prompt = prompt

        if one_line and height is not None:
            raise ValueError("If <one_line> is True, then <height> must be None.")

        style = (
            "" if width is None else f"width:{width}"
            " "
            "" if height is None else f"height:{height}"
        )

        super().__init__(
            time_allotted=time_allotted,
            template_str=get_template("text-input-page.html"),
            label=label,
            template_arg={
                "prompt": prompt,
                "one_line": one_line,
                "style": style
            }
        )

    def format_answer(self, answer, metadata, experiment, participant):
        return answer

    def process_response(self, response, metadata, experiment, participant, **kwargs):
        resp = Response(
            participant=participant,
            question_label=self.label, 
            answer=self.format_answer(response["answer"], metadata, experiment, participant),
            page_type=type(self).__name__,
            time_taken=metadata["time_taken"],
            details={
                "prompt": self.prompt
            }
        )
        participant.answer = resp.answer
        experiment.session.add(resp)
        experiment.save()
        return resp

    def validate(self, parsed_response, experiment, participant, **kwargs):
        pass

class NumberInputPage(TextInputPage):
    def format_answer(self, answer, metadata, experiment, participant):
        try:
            return float(answer)
        except ValueError:
            return "INVALID_RESPONSE"

    def validate(self, parsed_response, experiment, participant, **kwargs):
        if parsed_response.answer == "INVALID_RESPONSE":
            return FailedValidation("Please enter a number.")
        return None

class Timeline():
    def __init__(self, *args):
        elts = join(*args)
        self.elts = elts
        self.check_elts()        
        self.add_elt_ids()
        self.estimated_time_credit = self.estimate_time_credit()

    def check_elts(self):
        assert isinstance(self.elts, list)
        assert len(self.elts) > 0
        if not isinstance(self.elts[-1], EndPage):
            raise ValueError("The final element in the timeline must be a EndPage.")
        self.check_for_time_allotted()
        self.check_start_fix_times()

    def check_for_time_allotted(self):
        for i, elt in enumerate(self.elts):
            if (isinstance(elt, Page) or isinstance(elt, ReactivePage)) and elt.time_allotted is None:
                raise ValueError(f"Element {i} of the timeline was missing a time_allotted value.")

    def check_start_fix_times(self):
        try:
            _fix_time = False
            for i, elt in enumerate(self.elts):
                if isinstance(elt, StartFixTime):
                    assert not _fix_time
                    _fix_time = True
                elif isinstance(elt, EndFixTime):
                    assert _fix_time
                    _fix_time = False
        except AssertionError:
            raise ValueError(
                "Nested 'fix-time' constructs detected. This typically means you have "
                "nested conditionals or while loops with fix_time_credit=True. "
                "Such constructs cannot be nested; instead you should choose one level "
                "at which to set fix_time_credit=True."
            )

    def add_elt_ids(self):
        for i, elt in enumerate(self.elts):
            elt.id = i
        for i, elt in enumerate(self.elts):
            if elt.id != i:
                raise ValueError(
                    f"Failed to set unique IDs for each element in the timeline " +
                    f"(the element at 0-indexed position {i} ended up with the ID {elt.id}). " +
                    "This usually means that the same Python object instantiation is reused multiple times " +
                    "in the same timeline. This kind of reusing is not permitted, instead you should " +
                    "create a fresh instantiation of each element."
            )

    class Branch():
        def __init__(self, label: str, children: dict):
            self.label = label
            self.children = children

        def summarise(self, mode, wage_per_hour=None):
            return [
                self.label, 
                {key: child.summarise(mode, wage_per_hour) for key, child in self.children.items()}
            ]

        def get_max(self, mode, wage_per_hour=None):
            return max([
                child.get_max(mode, wage_per_hour) for child in self.children.values()
            ])

    class Leaf():
        def __init__(self, value: float):
            self.value = value

        def summarise(self, mode, wage_per_hour=None):
            if mode == "time":
                return self.value
            elif mode == "bonus":
                assert wage_per_hour is not None
                return self.value * wage_per_hour / (60 * 60)
            elif mode == "all":
                return {
                    "time_seconds": self.summarise(mode="time"),
                    "time_minutes": self.summarise(mode="time") / 60,
                    "time_hours": self.summarise(mode="time") / (60 * 60),
                    "bonus": self.summarise(mode="bonus", wage_per_hour=wage_per_hour)
                }

        def get_max(self, mode, wage_per_hour=None):
            return self.summarise(mode, wage_per_hour)

    def estimate_time_credit(self, starting_elt_id=0, starting_credit=0.0, starting_counter=0):
        elt_id = starting_elt_id
        time_credit = starting_credit
        counter = starting_counter

        while True:
            counter += 1
            if counter > 1e6:
                raise Exception("Got stuck in the estimate_time_credit() while loop, this shouldn't happen.")

            elt = self.elts[elt_id]

            # logger.info(f"elt_id = {elt_id}, elt = {elt}")

            if elt.returns_time_credit:
                time_credit += elt.time_allotted * elt.expected_repetitions
            
            if isinstance(elt, StartFixTime):
                elt_id = elt.end_fix_time.id

            elif isinstance(elt, EndFixTime):
                time_credit += elt.time_allotted * elt.expected_repetitions
                elt_id += 1

            elif isinstance(elt, StartSwitch) and elt.log_chosen_branch:
                return self.Branch(
                    label=elt.label,
                    children={
                        key: self.estimate_time_credit(
                            starting_elt_id=branch_start_elt.id, 
                            starting_credit=time_credit,
                            starting_counter=counter
                        )
                        for key, branch_start_elt in elt.branch_start_elts.items()
                    }
                )

            elif isinstance(elt, EndSwitchBranch):
                elt_id = elt.target.id

            elif isinstance(elt, EndPage):
                return self.Leaf(time_credit)

            else: 
                elt_id += 1

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

            # logger.info(f"participant.elt_id = {json.dumps(participant.elt_id)}")
        # logger.info(f"participant.branch_log = {json.dumps(participant.branch_log)}")

    # def process_response(self, response, experiment, participant):
    #     elt = self.get_current_elt(experiment, participant)
    #     parsed_response = elt.process_response(
    #         response=response,
    #         experiment=experiment,
    #         participant=participant
    #     )
    #     rpdb.set_trace()
    #     validation = elt.validate(
    #         parsed_response=parsed_response,
    #         experiment=experiment,
    #         participant=participant
    #     )
    #     parsed_response.successful_validation = validation is not RejectedResponse
    #     return validation

    # def estimate_total_time_credit(self):
    #     return estimate_time_credit(self.elts)

def estimate_time_credit(elts):
    return sum([
        elt.time_allotted * elt.expected_repetitions
        for elt in elts
        if elt.returns_time_credit
    ])
        
class FailedValidation:
    def __init__(self, message="Invalid response, please try again."):
        self.message = message

class Response(Question):
    __mapper_args__ = {"polymorphic_identity": "response"}

    answer = claim_field(1)
    time_taken = claim_field(2, float)
    page_type = claim_field(3, str)
    successful_validation = claim_field(4, bool)

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
        if not ((arg is None) or (isinstance(arg, (Elt, Module)) or is_list_of_elts(arg))):
            raise TypeError(f"Element {i + 1} of the input to join() was neither an Elt nor a list of Elts nor a Module ({arg}).")        

    if len(args) == 0:
        return []
    elif len(args) == 1 and isinstance(args[0], Elt):
        return [args[0]]
    else:
        def f(x, y):
            if isinstance(x, Module):
                x = x.resolve()
            if isinstance(y, Module):
                y = y.resolve()
            if x is None:
                return y
            elif y is None:
                return x
            elif isinstance(x, Elt) and isinstance(y, Elt):
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
    assert isinstance(logic, Elt) or is_list_of_elts(logic)
    if isinstance(logic, Elt):
        logic = [logic]
    if len(logic) == 0:
        raise ValueError("<logic> may not be empty.")
    return logic

class StartWhile(NullElt):
    def __init__(self, label):
        # targets = {
        #     True: self,
        #     False: end_while
        # }
        # super().__init__(condition, targets)
        super().__init__()
        self.label = label

class EndWhile(NullElt):
    def __init__(self, label):
        super().__init__()
        self.label = label

def while_loop(label, condition, logic, expected_repetitions: int, fix_time_credit=True):   
    start_while = StartWhile(label)
    end_while = EndWhile(label)

    logic = check_condition_and_logic(condition, logic)
    logic = multiply_expected_repetitions(logic, expected_repetitions)

    conditional_logic = join(logic, GoTo(start_while))

    elts = join(
        start_while,
        conditional(
            label, 
            condition, 
            conditional_logic, 
            fix_time_credit=False,
            log_chosen_branch=False
        ),
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

def switch(label, function, branches, fix_time_credit=True, log_chosen_branch=True):
    check_function_args(function, ("self", "experiment", "participant"), exact=False)
    branches = check_branches(branches)
   
    all_branch_starts = dict()
    all_elts = []
    final_elt = EndSwitch(label) 

    for branch_name, branch_elts in branches.items():
        branch_start = StartSwitchBranch(branch_name)
        branch_end = EndSwitchBranch(branch_name, final_elt)
        all_branch_starts[branch_name] = branch_start
        all_elts = all_elts + [branch_start] + branch_elts + [branch_end]

    start_switch = StartSwitch(label, function, branch_start_elts=all_branch_starts, log_chosen_branch=log_chosen_branch)
    combined_elts = [start_switch] + all_elts + [final_elt]

    if fix_time_credit:
        time_allotted = max([
            estimate_time_credit(branch_elts)
            for branch_elts in branches.values()
        ])
        return fix_time(combined_elts, time_allotted)
    else:
        return combined_elts

class StartSwitch(ReactiveGoTo):
    def __init__(self, label, function, branch_start_elts, log_chosen_branch=True):
        if log_chosen_branch:
            def function_2(experiment, participant):
                val = function(experiment, participant)
                log_entry = [label, val]
                participant.append_branch_log(log_entry)
                return val
            super().__init__(function_2, targets=branch_start_elts)
        else:
            super().__init__(function, targets=branch_start_elts)
        self.label = label
        self.branch_start_elts = branch_start_elts
        self.log_chosen_branch = log_chosen_branch

class EndSwitch(NullElt):
    def __init__(self, label):
        self.label = label

class StartSwitchBranch(NullElt):
    def __init__(self, name):
        super().__init__()
        self.name = name

class EndSwitchBranch(GoTo):
    def __init__(self, name, final_elt):
        super().__init__(target=final_elt)
        self.name = name

def conditional(
    label,
    condition, 
    logic_if_true, 
    logic_if_false=None, 
    fix_time_credit=True,
    log_chosen_branch=True
    ):
    return switch(
        label, 
        function=condition, 
        branches={
            True: logic_if_true,
            False: NullElt() if logic_if_false is None else logic_if_false
        }, 
        fix_time_credit=fix_time_credit,
        log_chosen_branch=log_chosen_branch
    )

class ConditionalElt(Elt):
    def __init__(self, label: str):
        self.label = label

class StartConditional(ConditionalElt):
    pass
    
class EndConditional(ConditionalElt):
    pass
   
def fix_time(elts, time_allotted):
    end_fix_time = EndFixTime(time_allotted)
    start_fix_time = StartFixTime(time_allotted, end_fix_time)
    return join(start_fix_time, elts, end_fix_time)

def multiply_expected_repetitions(logic, factor: float):
    assert isinstance(logic, Elt) or is_list_of_elts(logic)
    if isinstance(logic, Elt):
        logic.multiply_expected_repetitions(factor)
    else:
        for elt in logic:
            elt.multiply_expected_repetitions(factor)
    return logic

class ProgressBar():
    def __init__(self, progress: float, show=True, min_pct=5, max_pct=99):
        self.show = show
        self.percentage = round(progress * 100)
        if self.percentage > max_pct:
            self.percentage = max_pct
        elif self.percentage < min_pct:
            self.percentage = min_pct

class Footer():
    def __init__(self, text_to_show: List[str], escape=True, show=True):
        self.show = show
        self.text_to_show = [x if escape else flask.Markup(x) for x in text_to_show]

class Module():
    default_label = None
    default_elts = None

    def __init__(self, label: str = None, elts: list = None):
        if self.default_label is None and label is None:
            raise ValueError("Either one of <default_label> or <label> must not be none.")
        if self.default_elts is None and elts is None:
            raise ValueError("Either one of <default_elts> or <elts> must not be none.")

        self.label = label if label is not None else self.default_label
        self.elts = elts if elts is not None else self.default_elts

    def resolve(self):
        return join(
            StartModule(self.label),
            self.elts,
            EndModule(self.label)
        )

class StartModule(NullElt):
    def __init__(self, label):
        super().__init__()
        self.label = label

class EndModule(NullElt):
    def __init__(self, label):
        super().__init__()
        self.label = label

class ExperimentSetupRoutine(NullElt):
    def __init__(self, function):
        self.check_function(function)
        self.function = function

    def check_function(self, function):
        if not self._is_function(function) and check_function_args(function, ["experiment"]):
            raise TypeError("<function> must be a function or method of the form f(experiment).")

    @staticmethod
    def _is_function(x):
        return callable(x)

class BackgroundTask(NullElt):
    def __init__(self, label, function, interval_sec, run_on_launch=False):
        check_function_args(function, args=[])
        self.label = label
        self.function = function
        self.interval_sec = interval_sec
        self.run_on_launch = run_on_launch

    def safe_function(self):
        start_time = time.monotonic()
        logger.info("Executing the background task '%s'...", self.label)
        try:
            self.function()
            end_time = time.monotonic()
            time_taken = end_time - start_time
            logger.info("The background task '%s' completed in %s seconds.", self.label, f"{time_taken:.3f}")
        except Exception:
            logger.info("An exception was thrown in the background task '%s'.", self.label, exc_info=True)

    def daemon(self):
        if self.run_on_launch:
            self.safe_function()
        while True:
            gevent.sleep(self.interval_sec)
            self.safe_function()

# class RegisterBackgroundTasks(NullElt):
#     def __init__(self, tasks):
#         assert isinstance(tasks, list)
#         for task in tasks:
#             assert isinstance(task, BackgroundTask)
#         self.tasks = tasks
