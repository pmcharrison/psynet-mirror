import importlib_resources
import flask

from .utils import dict_to_js_vars
from . import templates

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
        template_path=None,
        template_str=None, 
        template_arg={},
        label="untitled",
        on_complete=lambda: None,
        validate=lambda: None,
        js_vars = {}
    ):
        if template_path is None and template_str is None:
            raise ValueError("Must provide either template_path or template_str.")
        if template_path is not None and template_str is not None:
            raise ValueError("Cannot provide both template_path and template_str.")

        if template_path is not None:
            with open(template_path, "r") as file:
                template_str = file.read()

        assert isinstance(template_arg, dict)
        assert isinstance(label, str)
        assert callable(on_complete)

        self.template_str = template_str
        self.template_arg = template_arg
        self.label = label
        self.on_complete = on_complete
        self.js_vars = js_vars

    def render(self, experiment, participant):
        internal_js_vars = {
            "page_uuid": participant.page_uuid
        }
        all_template_arg = {
            **self.template_arg, 
            "init_js_vars": flask.Markup(dict_to_js_vars({**self.js_vars, **internal_js_vars}))
        }
        return flask.render_template_string(self.template_str, **all_template_arg)

    def process_response(self, data, participant):
        pass

class ReactivePage(Elt):
    def __init__(self, function):
        self.function = function

    def resolve(self, experiment, participant):
        page = self.function(experiment=experiment, participant=participant)
        if not isinstance(page, Page):
            raise TypeError("The ReactivePage function must return an object of class Page.")
        return page

    # def render(self, experiment, participant):
    #     page = self.resolve(experiment=experiment, participant=participant)
    #     return page.render(experiment=experiment, participant=participant)

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

# class BeginPage(Page):
#     def __init__(self, content="Starting experiment... (try refreshing if nothing happens after 5 seconds)", title="", **kwargs):
#         super().__init__(
#             template_str=get_template("begin.html"),
#             template_arg={
#                 "content": content,
#                 "title": title
#             },
#             **kwargs
#         )

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
            if new_elt is CodeBlock:
                new_elt.execute(experiment, participant)
            else:
                participant.page_uuid = experiment.make_uuid()
                finished = True

        
class RejectedResponse:
    def __init__(self, message="Invalid response, please try again."):
        self.message = message
        