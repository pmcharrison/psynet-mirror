import importlib_resources
import flask

from . import templates

def get_template(name):
    assert isinstance(name, str)
    return importlib_resources.read_text(templates, name)

class Page:
    def __init__(
        self,
        template_path=None,
        template_str=None, 
        template_arg={},
        label="untitled",
        on_complete=lambda: None,

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
