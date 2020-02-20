import importlib_resources
import flask

from . import templates

def get_template(name):
    assert isinstance(name, str)
    return importlib_resources.read_text(templates, name)

class Elt:
    pass

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
        validate=lambda: None

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

    def render(self):
        return flask.render_template_string(self.template_str, **self.template_arg)

    def process_response(self, data, participant):
        pass

class ReactivePage(Elt):
    pass

class InfoPage(Page):
    def __init__(self, content, title=None, **kwargs):
        super().__init__(
            template_str=get_template("info-page.html"),
            template_arg={
                "content": content,
                "title": title
            },
            **kwargs
        )

class BeginPage(Page):
    def __init__(self, content="Welcome to the experiment!", title="Welcome", **kwargs):
        super().__init__(
            template_str=get_template("begin.html"),
            template_arg={
                "content": content,
                "title": title
            },
            **kwargs
        )

class Timeline():
    def __init__(self, elts):
        self.elts = elts
        self.check_elts(elts)        

    def check_elts(self, elts):
        assert isinstance(elts, list)
        assert len(elts) > 0
        assert isinstance(elts[-1], Page) or isinstance(elts[-1], ReactivePage)

    def __len__(self):
        return len(self.elts)

    def __getitem__(self, key):
        return self.elts[key]

    def get_current_elt(self, participant):
        n = participant.elt_id 
        N = len(self)
        if n >= N:
            raise ValueError(f"Tried to get element {n + 1} of a timeline with only {N} element(s).")
        else:
            return self[n]

    def advance_page(self, experiment, participant):
        finished = False
        while not finished:
            participant.elt_id += 1
            new_elt = self.get_current_elt(participant)
            if new_elt is CodeBlock:
                new_elt.execute(experiment, participant)
            else:
                finished = True

        
class RejectedResponse:
    def __init__(self, message="Invalid response, please try again."):
        self.message = message
        