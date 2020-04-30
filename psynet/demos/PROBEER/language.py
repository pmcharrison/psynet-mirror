from psynet.page import (
    Page
)
from flask import Markup

from typing import (
    Union,
    Optional
)
import os
import json

def get_template(name):
    assert isinstance(name, str)
    data_path = os.path.join('templates', name)
    with open(data_path, encoding='utf-8') as fp:
        template_str = fp.read()
    return template_str

class LanguagePage(Page):
        """
        This page solicits a text response from the user.
        By default this response is saved in the database as a
        :class:`psynet.timeline.Response` object,
        which can be found in the ``Questions`` table.

        Parameters
        ----------

        label:
            Internal label for the page (used to store results).

        prompt:
            Prompt to display to the user. Use :class:`flask.Markup`
            to display raw HTML.

        time_estimate:
            Time estimated for the page.

        **kwargs:
            Further arguments to pass to :class:`psynet.timeline.Page`.
        """

        def __init__(
                self,
                label: str,
                prompt: str,
                time_estimate: float,
                **kwargs
        ):
            self.prompt = prompt
            with open('languages.json', 'r') as f:
                languages = json.load(f)
            super().__init__(
                time_estimate=time_estimate,
                template_str=get_template("language-input-page.html"),
                label=label,
                template_arg={
                    "prompt": prompt,
                    "languages": languages
                },
                **kwargs
            )

        def metadata(self, **kwargs):
            # pylint: disable=unused-argument
            return {
                "prompt": self.prompt
            }
