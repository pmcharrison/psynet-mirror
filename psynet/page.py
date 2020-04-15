from flask import Markup

from typing import (
    Union, 
    Optional,
    List
)

from .timeline import(
    get_template,
    Page,
    EndPage,
    FailedValidation  
)

class InfoPage(Page): 
    """
    This page displays some content to the user alongside a button
    with which to advance to the next page.

    Parameters
    ----------

    content:
        The content to display to the user. Use :class:`flask.Markup`
        to display raw HTML.

    time_estimate:
        Time estimated for the page.

    **kwargs:
        Further arguments to pass to :class:`psynet.timeline.Page`.
    """

    def __init__(
        self, 
        content: Union[str, Markup], 
        time_estimate: Optional[float] = None,
        **kwargs
    ):
        self.content = content
        super().__init__(
            time_estimate=time_estimate,
            template_str=get_template("info-page.html"),
            template_arg={
                "content": "" if content is None else content
            },
            **kwargs
        )
        
    def metadata(self, **kwargs):
        return {
            "content": self.content
        }
        
class SuccessfulEndPage(EndPage):
    """
    Indicates a successful end to the experiment.
    """
    def finalise_participant(self, experiment, participant):
        participant.complete = True

class UnsuccessfulEndPage(EndPage):
    """
    Indicates an unsuccessful end to the experiment.
    """
    def __init__(self, content="default", failure_tags: Optional[List] = None):
        if content=="default":
            content = (
                "Unfortunately you did not meet the criteria to continue in the experiment. "
                "You will still be paid for the time you spent already. "
                "Thank you for taking part!"
            )
        super().__init__(content=content)
        self.failure_tags = failure_tags

    def finalise_participant(self, experiment, participant):
        if self.failure_tags:
            assert isinstance(self.failure_tags, list)
            participant.append_failure_tags(*self.failure_tags)
        experiment.fail_participant(participant)

class NAFCPage(Page):
    """
    This page solicits a multiple-choice response from the participant.
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

    choices:
        The different options the participant has to choose from.

    time_estimate:
        Time estimated for the page.

    labels:
        An optional list of textual labels to apply to the buttons, 
        which the participant will see instead of ``choices``.

    arrange_vertically:
        Whether to arrange the buttons vertically.

    min_width:
        CSS ``min_width`` parameter for the buttons.   
        
    **kwargs:
        Further arguments to pass to :class:`psynet.timeline.Page`.
    """

    def __init__(
        self,
        label: str,
        prompt: Union[str, Markup],
        choices: List[str],        
        time_estimate: Optional[float] = None,
        labels: Optional[List[str]] = None,
        arrange_vertically: bool = False,
        min_width: str ="100px",
        **kwargs
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
            time_estimate=time_estimate,
            template_str=get_template("nafc-page.html"),
            label=label,
            template_arg={
                "prompt": prompt,
                "buttons": buttons
            },
            **kwargs
        )

    def metadata(self, **kwargs):
        # pylint: disable=unused-argument
        return {
            "prompt": self.prompt,
            "choices": self.choices,
            "labels": self.labels
        }

class TextInputPage(Page):
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

    one_line:
        Whether the text box should comprise solely one line.

    width:
        Optional CSS width property for the text box.

    height:
        Optional CSS height property for the text box.
        
    **kwargs:
        Further arguments to pass to :class:`psynet.timeline.Page`.
    """
    def __init__(
        self,
        label: str,
        prompt: Union[str, Markup],     
        time_estimate: Optional[float] = None,
        one_line: bool = True,
        width: Optional[str] = None, # e.g. "100px"
        height: Optional[str] = None,
        **kwargs
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
            time_estimate=time_estimate,
            template_str=get_template("text-input-page.html"),
            label=label,
            template_arg={
                "prompt": prompt,
                "one_line": one_line,
                "style": style
            },
            **kwargs
        )

    def metadata(self, **kwargs):
        # pylint: disable=unused-argument
        return {
            "prompt": self.prompt
        }

class SliderInputPage(Page):
    """
    This page solicits a slider response from the user.
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

    time_allotted:
        Time allotted for the page.

    min_value:
        Minimal value of the slider.

    max_value:
        Maximum value of the slider.

    step_size:
        The size of each step in the slider.

    width:
        Optional CSS width property for the text box.

    height:
        Optional CSS height property for the text box.
        
    **kwargs:
        Further arguments to pass to :class:`psynet.timeline.Page`.
    """
    def __init__(
        self,
        label: str,
        prompt: Union[str, Markup],
        time_allotted: Optional[float] = None,
        min_value: Optional[int] = 0,
        max_value: Optional[int] = 100,
        step_size: Optional[int] = 1,
        width: Optional[str] = None, # e.g. "100px"
        height: Optional[str] = None,
        **kwargs
    ):

        if max_value <= min_value:
            raise ValueError("<max_value> must be larger than <min_value>")

        if (max_value - min_value) <= step_size*2:
            raise ValueError("For the given <min_value> and <max_value> values the <step_size> needs to be appropriate, i.e. allow at least 2 steps on the slider.")

        self.prompt = prompt

        style = (
            "" if width is None else f"width:{width}"
            " "
            "" if height is None else f"height:{height}"
        )

        super().__init__(
            time_allotted=time_allotted,
            template_str=get_template("slider-input-page.html"),
            label=label,
            template_arg={
                "prompt": prompt,
                "step_size": step_size,
                "min_value": min_value,
                "max_value": max_value,
                "style": style
            },
            **kwargs
        )
    
    def metadata(self, **kwargs):
        # pylint: disable=unused-argument
        return {
            "prompt": self.prompt
        }

class NumberInputPage(TextInputPage):
    """
    This page is like :class:`psynet.timeline.TextInputPage`,
    except it forces the user to input a number.
    See :class:`psynet.timeline.TextInputPage` for argument documentation.
    """

    def format_answer(self, raw_answer, **kwargs):
        try:
            return float(raw_answer)
        except ValueError:
            return "INVALID_RESPONSE"

    def validate(self, response, **kwargs):
        if response.answer == "INVALID_RESPONSE":
            return FailedValidation("Please enter a number.")
        return None

class Button():
    def __init__(self, button_id, label, min_width, start_disabled=False):
        self.id = button_id
        self.label = label
        self.min_width = min_width
        self.start_disabled = start_disabled
        