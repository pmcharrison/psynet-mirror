from typing import Optional

from .timeline import Page, get_template


class StandardConsentPage(Page):
    """
    This page displays the standard consent page.

    Parameters
    ----------

    time_estimate:
        Time estimated for the page.

    **kwargs:
        Further arguments to pass to :class:`psynet.timeline.Page`.
    """

    def __init__(
        self,
        time_estimate: Optional[float] = None,
        **kwargs,
    ):
        super().__init__(
            time_estimate=time_estimate,
            template_str=get_template("standard_consent.html"),
            **kwargs,
        )

    def format_answer(self, raw_answer, **kwargs):
        return {"participant_consent": True}


class AudiovisualRecordingsConsentPage(Page):
    """
    This page displays the audiovisual recordings consent page.

    Parameters
    ----------

    time_estimate:
        Time estimated for the page.

    **kwargs:
        Further arguments to pass to :class:`psynet.timeline.Page`.
    """

    def __init__(
        self,
        time_estimate: Optional[float] = None,
        **kwargs,
    ):
        super().__init__(
            time_estimate=time_estimate,
            template_str=get_template("audiovisual_recordings_consent.html"),
            **kwargs,
        )

    def format_answer(self, raw_answer, **kwargs):
        return {"participant_consent": True}
